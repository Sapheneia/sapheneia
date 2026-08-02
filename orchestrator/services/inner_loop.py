"""Per-iteration backtest loop. One call per run_id."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime

from shared.contracts import ForecastEnvelope
from shared.timeutils import to_utc_date, to_utc_datetime

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
        max_per_model: int = 2,
        heartbeat_interval: float = 30.0,
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
        self.max_per_model = max_per_model
        self.heartbeat_interval = heartbeat_interval

    async def run(self, run_id: str, cfg: StrategyConfig, experiment_id: str) -> None:
        logger.info("Run %s starting", run_id)
        # Heartbeat on wall-clock, not iteration count. A single iteration can
        # block for the full forecast timeout, so an every-N-iterations
        # heartbeat can exceed the reconciler's stale threshold and get a live
        # run marked `failed` underneath us.
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(run_id))
        try:
            await self.runs.update_status(run_id, "running")
            prices = await self._fetch_prices(cfg)
            if not prices:
                raise RuntimeError("data service returned no prices for evaluation window")

            eval_start = cfg.evaluation.parse_date("start_date")
            eval_end = cfg.evaluation.parse_date("end_date")
            eval_dates = [
                p["time"] for p in prices if eval_start <= to_utc_date(p["time"]) <= eval_end
            ]
            if not eval_dates:
                raise RuntimeError("no prices in evaluation window")

            portfolio = Portfolio(
                cash=cfg.trading.initial_cash or cfg.trading.initial_capital,
                position=cfg.trading.initial_position,
                initial_capital=cfg.trading.initial_capital,
            )
            equity_curve: list[tuple[datetime, float]] = []

            for iter_idx, as_of_raw in enumerate(eval_dates):
                as_of = to_utc_datetime(as_of_raw)
                context = self._context_window(prices, as_of, cfg.forecast.context_size)
                if len(context) < 2:
                    continue

                forecast = await self._maybe_cached_forecast(
                    cfg, run_id, experiment_id, as_of, context
                )
                forecast_price = forecast.price_at_horizon(cfg.trading.horizon)
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

            returns = _equity_to_returns([eq for _, eq in equity_curve])
            metrics_payload: dict = {}
            if returns:
                resp = await self.metrics_client.compute(returns=returns, request_id=run_id)
                metrics_payload = _normalise_metrics(resp)
            await self.metrics.write(run_id, metrics_payload)
            await self.runs.update_status(run_id, "completed", completed=True, clear_error=True)
            logger.info("Run %s completed (%d iterations)", run_id, len(equity_curve))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Run %s failed", run_id)
            await self.runs.update_status(run_id, "failed", error=str(exc), completed=True)
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

    # ---- helpers --------------------------------------------------------

    async def _heartbeat_loop(self, run_id: str) -> None:
        """Refresh this run's heartbeat on a fixed wall-clock cadence."""
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            try:
                await self.runs.heartbeat(run_id)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.warning("Heartbeat failed for run %s", run_id, exc_info=True)

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
    ) -> ForecastEnvelope:
        hit = await cache_service.lookup(
            self.forecasts, cfg=cfg, experiment_id=experiment_id, time=as_of
        )
        if hit:
            return cache_service.envelope_from_row(cfg, hit)

        sem = self.per_model_semaphores.setdefault(
            cfg.forecast.model, asyncio.Semaphore(self.max_per_model)
        )
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
        as_of_d = to_utc_date(as_of)
        rows = [p for p in prices if to_utc_date(p["time"]) < as_of_d]
        rows = rows[-size:]
        return [float(r["close"]) for r in rows if r.get("close") is not None]

    def _latest_price(self, prices: list[dict], as_of: datetime) -> float:
        as_of_d = to_utc_date(as_of)
        rows = [
            p for p in prices if to_utc_date(p["time"]) <= as_of_d and p.get("close") is not None
        ]
        return float(rows[-1]["close"]) if rows else 0.0


def _equity_to_returns(equity: list[float]) -> list[float]:
    out: list[float] = []
    for prev, curr in zip(equity, equity[1:], strict=False):
        if prev > 0:
            out.append((curr - prev) / prev)
    return out


#: Columns the metrics table stores natively; anything else lands in ``extra``.
_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "sharpe": ("sharpe_ratio", "sharpe"),
    "sortino": ("sortino_ratio", "sortino"),
    "cagr": ("cagr",),
    "calmar": ("calmar_ratio", "calmar"),
    "max_drawdown": ("max_drawdown",),
    "win_rate": ("win_rate",),
    "total_return": ("total_return",),
}

_NON_EXTRA_KEYS = {alias for aliases in _METRIC_ALIASES.values() for alias in aliases} | {
    "interpretation",
    "metadata",
}


def _normalise_metrics(metrics_response: dict) -> dict:
    """Map metrics service response into our metrics table columns."""
    if "metrics" in metrics_response and isinstance(metrics_response["metrics"], dict):
        m = metrics_response["metrics"]
    else:
        m = metrics_response
    out: dict = {}
    for column, aliases in _METRIC_ALIASES.items():
        value = next((m[a] for a in aliases if m.get(a) is not None), None)
        out[column] = value
    extras = {k: v for k, v in m.items() if k not in _NON_EXTRA_KEYS}
    if extras:
        out["extra"] = extras
    return out
