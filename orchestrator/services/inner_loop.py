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

#: Bar fields the history-needing strategies' request arrays are built from.
_OHLC_FIELDS: tuple[str, ...] = ("open", "high", "low", "close")
#: The runtime array keys the orchestrator owns (config keys like
#: ``window_history``/``which_history`` also end in "_history" — match exactly).
_OHLC_HISTORY_KEYS: frozenset[str] = frozenset(f"{f}_history" for f in _OHLC_FIELDS)


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
            if self._needs_price_history(cfg.trading.strategy_type, cfg.trading.params):
                # Static config check, hoisted so a misconfigured run fails
                # before paying a price fetch and a forecast round-trip (up to
                # the full forecast timeout on a cache miss).
                self._history_window(cfg.trading.strategy_type, cfg.trading.params)
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
                    params=self._trade_params(cfg, prices, as_of),
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

    def _trade_params(self, cfg: StrategyConfig, prices: list[dict], as_of: datetime) -> dict:
        """Assemble the per-iteration trading params from config plus market data.

        The trading service is pure compute (§4.3): it has no data client and
        receives everything in the request. Every strategy variant whose schema
        demands price-history arrays therefore needs the orchestrator — the
        assembler that already holds the fetched bars — to supply them; without
        them each such request 422s on the trading schema's validators. That is
        quantile always, threshold with ``threshold_type`` "atr" (schema-required)
        or "std_dev" (silently falls back to an absolute threshold without
        history), and return with ``position_sizing`` "normalized" (§5.4: one
        bug class, fixed at every variant it applies to).

        Keyed on ``strategy_type`` and its params, never on ``model_id``: which
        market context a strategy needs is a property of the strategy, not of
        the forecasting model (§3.5). Variants that need no history — plain
        threshold, fixed/proportional return — get the config params verbatim,
        as before.
        """
        params = dict(cfg.trading.params)
        if self._needs_price_history(cfg.trading.strategy_type, params):
            embedded = sorted(k for k in params if k in _OHLC_HISTORY_KEYS)
            if embedded:
                # Overwriting these silently would make a config that used to
                # "work" (static arrays passing the schema) compute different
                # numbers without a trace. History is runtime market data the
                # orchestrator assembles per iteration; static history in a
                # backtest config is almost certainly a mistake.
                raise RuntimeError(
                    f"trading.params must not embed price history ({', '.join(embedded)}); "
                    "the orchestrator assembles OHLC arrays per iteration from fetched bars"
                )
            window = self._history_window(cfg.trading.strategy_type, params)
            params.update(self._ohlc_history(prices, as_of, window))
        return params

    @staticmethod
    def _needs_price_history(strategy_type: str, params: dict) -> bool:
        """Whether this strategy variant's trading request needs OHLC arrays."""
        if strategy_type == "quantile":
            return True
        if strategy_type == "threshold":
            return params.get("threshold_type") in ("atr", "std_dev")
        if strategy_type == "return":
            return params.get("position_sizing") == "normalized"
        return False

    @staticmethod
    def _history_window(strategy_type: str, params: dict) -> int | None:
        """The validated lookback window for a history-needing variant.

        Quantile requires ``window_history`` (the trading schema has no default
        for it); failing loudly here beats letting ``bars[-0:]`` silently ship
        the whole price history alongside a config the schema rejects anyway.
        For threshold/return the field is optional with a service-side default,
        so ``None`` means "send every bar up to as_of and let the service apply
        its own window slice" — the service slices ``[-window_history:]`` in all
        four code paths, and duplicating its default constant here would be
        §3.5 drift.
        """
        window = params.get("window_history")
        if window is None:
            if strategy_type == "quantile":
                raise RuntimeError(
                    "quantile strategy requires a positive integer trading.params.window_history"
                )
            return None
        if not isinstance(window, int) or window <= 0:
            raise RuntimeError(
                f"{strategy_type} strategy requires trading.params.window_history "
                "to be a positive integer when set"
            )
        return window

    def _ohlc_history(
        self, prices: list[dict], as_of: datetime, window: int | None
    ) -> dict[str, list[float]]:
        """The last ``window`` complete OHLC bars ending at ``as_of``.

        No look-ahead: only bars with time <= as_of, matching ``_latest_price``
        (the bar being traded on is part of the observable history). Bars with
        any missing OHLC field are skipped so the four arrays stay equal-length,
        which the trading schema validates. The trading service itself slices
        ``[-window_history:]`` and degrades to hold below its minimum history,
        so sending fewer than ``window`` bars early in a run is safe — but zero
        usable bars is not: the quantile schema accepts empty arrays and the
        service would then hold every iteration, "completing" the run with a
        flat equity curve and meaningless metrics (threshold/return reject
        empty arrays outright). A close-only price source must fail the run,
        not silently hold through it. ``window=None`` sends every usable bar
        up to ``as_of``; the service applies its own window slice.
        """
        as_of_d = to_utc_date(as_of)
        bars = [
            p
            for p in prices
            if to_utc_date(p["time"]) <= as_of_d
            and all(p.get(field) is not None for field in _OHLC_FIELDS)
        ]
        if window is not None:
            bars = bars[-window:]
        if not bars:
            raise RuntimeError(
                "this strategy requires OHLC price data; the price source "
                "returned no bars with complete open/high/low/close values"
            )
        return {f"{field}_history": [float(b[field]) for b in bars] for field in _OHLC_FIELDS}


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
