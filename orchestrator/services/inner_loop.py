"""Per-iteration backtest loop. One call per run_id."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

from ..clients.data_client import DataClient
from ..clients.forecast_client import ForecastClient
from ..clients.metrics_client import MetricsClient
from ..clients.trading_client import TradingClient
from ..repositories.forecasts_repo import ForecastsRepository
from ..repositories.runs_repo import MetricsRepository, RunsRepository
from ..repositories.trades_repo import EquityRepository, TradesRepository
from ..schemas.strategy import StrategyConfig
from . import cache_service
from .portfolio import Portfolio

logger = logging.getLogger("sapheneia.orchestrator.loop")


class InnerLoop:
    def __init__(
        self,
        *,
        data_client: DataClient,
        forecast_client: ForecastClient,
        trading_client: TradingClient,
        metrics_client: MetricsClient,
        runs_repo: RunsRepository,
        forecasts_repo: ForecastsRepository,
        trades_repo: TradesRepository,
        equity_repo: EquityRepository,
        metrics_repo: MetricsRepository,
        per_model_semaphores: dict[str, asyncio.Semaphore],
    ):
        self.data_client = data_client
        self.forecast_client = forecast_client
        self.trading_client = trading_client
        self.metrics_client = metrics_client
        self.runs = runs_repo
        self.forecasts = forecasts_repo
        self.trades = trades_repo
        self.equity = equity_repo
        self.metrics = metrics_repo
        self.per_model_semaphores = per_model_semaphores

    async def run(self, run_id: str, cfg: StrategyConfig, experiment_id: str) -> None:
        logger.info("Run %s starting", run_id)
        try:
            await self.runs.update_status(run_id, "running")
            prices = await self._fetch_prices(cfg)
            if not prices:
                raise RuntimeError("data service returned no prices for evaluation window")

            eval_start = cfg.evaluation.parse_date("start_date")
            eval_end = cfg.evaluation.parse_date("end_date")
            eval_dates = [
                p["time"] for p in prices if eval_start <= _to_date(p["time"]) <= eval_end
            ]
            if not eval_dates:
                raise RuntimeError("no prices in evaluation window")

            portfolio = Portfolio(
                cash=cfg.trading.initial_cash or cfg.trading.initial_capital,
                position=cfg.trading.initial_position,
                initial_capital=cfg.trading.initial_capital,
            )
            equity_curve: list[tuple[datetime, float]] = []

            for iter_idx, as_of in enumerate(eval_dates):
                context = self._context_window(prices, as_of, cfg.forecast.context_size)
                if len(context) < 2:
                    continue

                forecast = await self._maybe_cached_forecast(
                    cfg, run_id, experiment_id, as_of, context
                )
                forecast_price = self._pick_forecast_price(forecast, cfg.trading.horizon)
                current_price = float(self._latest_price(prices, as_of))

                trade = await self.trading_client.execute(
                    strategy_type=cfg.trading.strategy_type,
                    params=cfg.trading.params,
                    forecast_price=forecast_price,
                    current_price=current_price,
                    current_position=portfolio.position,
                    available_cash=portfolio.cash,
                    initial_capital=cfg.trading.initial_capital,
                    request_id=run_id,
                )
                portfolio.apply_trade(
                    trade.get("action", "HOLD"),
                    float(trade.get("size", 0.0) or 0.0),
                    float(trade.get("value", 0.0) or 0.0),
                )

                eq = portfolio.equity(current_price)
                await self.trades.write(
                    run_id=run_id,
                    iteration_idx=iter_idx,
                    time=as_of,
                    ticker=cfg.evaluation.ticker,
                    action=trade.get("action", "HOLD"),
                    size=float(trade.get("size", 0.0) or 0.0),
                    price=current_price,
                    value=float(trade.get("value", 0.0) or 0.0),
                    reason=trade.get("reason"),
                )
                await self.equity.write(
                    run_id=run_id,
                    time=as_of,
                    cash=portfolio.cash,
                    position=portfolio.position,
                    equity=eq,
                )
                equity_curve.append((as_of, eq))

                if iter_idx % 10 == 0:
                    await self.runs.heartbeat(run_id)

            returns = _equity_to_returns([eq for _, eq in equity_curve])
            metrics_payload: dict = {}
            if returns:
                resp = await self.metrics_client.compute(returns=returns, request_id=run_id)
                metrics_payload = _normalise_metrics(resp)
            await self.metrics.write(run_id, metrics_payload)
            await self.runs.update_status(run_id, "completed", completed=True)
            logger.info("Run %s completed (%d iterations)", run_id, len(equity_curve))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Run %s failed", run_id)
            await self.runs.update_status(run_id, "failed", error=str(exc), completed=True)

    # ---- helpers --------------------------------------------------------

    async def _fetch_prices(self, cfg: StrategyConfig) -> list[dict]:
        return await self.data_client.get_prices(
            ticker=cfg.evaluation.ticker,
            start=cfg.evaluation.parse_date("fetch_start_date"),
            end=cfg.evaluation.parse_date("end_date"),
            end_date=cfg.evaluation.parse_date("end_date"),
        )

    async def _maybe_cached_forecast(
        self,
        cfg: StrategyConfig,
        run_id: str,
        experiment_id: str,
        as_of: datetime,
        context: list[float],
    ) -> dict:
        hit = await cache_service.lookup(
            self.forecasts, cfg=cfg, experiment_id=experiment_id, time=as_of
        )
        if hit:
            return {
                "median": hit["median"],
                "q10": hit.get("q10"),
                "q90": hit.get("q90"),
                "_cache_hit": True,
            }

        sem = self.per_model_semaphores.setdefault(cfg.forecast.model, asyncio.Semaphore(2))
        async with sem:
            forecast = await self.forecast_client.predict(
                model_id=cfg.forecast.model,
                context=context,
                horizon=cfg.forecast.forecast_horizon,
                request_id=run_id,
            )
        await cache_service.write(
            self.forecasts, cfg=cfg, run_id=run_id, time=as_of, forecast=forecast
        )
        return forecast

    def _context_window(self, prices: list[dict], as_of: datetime, size: int) -> list[float]:
        as_of_d = _to_date(as_of)
        rows = [p for p in prices if _to_date(p["time"]) < as_of_d]
        rows = rows[-size:]
        return [float(r["close"]) for r in rows if r.get("close") is not None]

    def _latest_price(self, prices: list[dict], as_of: datetime) -> float:
        as_of_d = _to_date(as_of)
        rows = [p for p in prices if _to_date(p["time"]) <= as_of_d and p.get("close") is not None]
        return float(rows[-1]["close"]) if rows else 0.0

    def _pick_forecast_price(self, forecast: dict, trading_horizon: int) -> float:
        median = forecast.get("median")
        if median is None:
            median = (forecast.get("forecast") or {}).get("values")
        if median is None:
            median = (forecast.get("prediction") or {}).get("median")
        if not median:
            return 0.0
        if isinstance(median[0], list):
            median = median[0]
        idx = max(0, min(int(trading_horizon) - 1, len(median) - 1))
        return float(median[idx])


def _to_date(t) -> date:
    if isinstance(t, datetime):
        return t.date()
    if isinstance(t, date):
        return t
    return datetime.fromisoformat(str(t)).date()


def _equity_to_returns(equity: list[float]) -> list[float]:
    out: list[float] = []
    for prev, curr in zip(equity, equity[1:]):
        if prev > 0:
            out.append((curr - prev) / prev)
    return out


def _normalise_metrics(metrics_response: dict) -> dict:
    """Map metrics service response into our metrics table columns."""
    if "metrics" in metrics_response and isinstance(metrics_response["metrics"], dict):
        m = metrics_response["metrics"]
    else:
        m = metrics_response
    out = {
        "sharpe": m.get("sharpe_ratio") or m.get("sharpe"),
        "sortino": m.get("sortino_ratio") or m.get("sortino"),
        "cagr": m.get("cagr"),
        "calmar": m.get("calmar_ratio") or m.get("calmar"),
        "max_drawdown": m.get("max_drawdown"),
        "win_rate": m.get("win_rate"),
        "total_return": m.get("total_return"),
    }
    extras = {
        k: v
        for k, v in m.items()
        if k
        not in {
            "sharpe_ratio",
            "sharpe",
            "sortino_ratio",
            "sortino",
            "cagr",
            "calmar_ratio",
            "calmar",
            "max_drawdown",
            "win_rate",
            "total_return",
            "interpretation",
            "metadata",
        }
    }
    if extras:
        out["extra"] = extras
    return out
