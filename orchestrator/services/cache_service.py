"""Forecast-cache lookup logic, scope-aware."""

from __future__ import annotations

from datetime import datetime

from ..repositories.forecasts_repo import ForecastsRepository
from ..schemas.strategy import StrategyConfig


async def lookup(
    repo: ForecastsRepository,
    *,
    cfg: StrategyConfig,
    experiment_id: str,
    time: datetime,
) -> dict | None:
    if not cfg.cache.enabled or "forecasts" not in cfg.cache.what:
        return None
    scope_eid = experiment_id if cfg.cache.scope == "experiment" else None
    return await repo.lookup(
        model_id=cfg.forecast.model,
        ticker=cfg.evaluation.ticker,
        time=time,
        context_size=cfg.forecast.context_size,
        horizon_size=cfg.forecast.forecast_horizon,
        experiment_id=scope_eid,
    )


async def write(
    repo: ForecastsRepository,
    *,
    cfg: StrategyConfig,
    run_id: str,
    time: datetime,
    forecast: dict,
) -> None:
    if not cfg.cache.enabled or "forecasts" not in cfg.cache.what:
        return
    median = _flatten(forecast.get("median") or forecast.get("forecast", {}).get("values"))
    q10 = _quantile(forecast, 0.1)
    q90 = _quantile(forecast, 0.9)
    if median is None:
        return
    await repo.write(
        run_id=run_id,
        ticker=cfg.evaluation.ticker,
        time=time,
        model_id=cfg.forecast.model,
        context_size=cfg.forecast.context_size,
        horizon_size=cfg.forecast.forecast_horizon,
        median=list(median),
        q10=list(q10) if q10 is not None else None,
        q90=list(q90) if q90 is not None else None,
    )


def _flatten(values) -> list[float] | None:
    if values is None:
        return None
    if values and isinstance(values[0], list):
        return [float(v) for v in values[0]]
    return [float(v) for v in values]


def _quantile(forecast: dict, q: float) -> list[float] | None:
    quantiles = forecast.get("quantiles") or []
    for entry in quantiles:
        if abs(float(entry.get("quantile", -1)) - q) < 1e-6:
            return _flatten(entry.get("values"))
    legacy = forecast.get("prediction", {}).get("quantiles") if isinstance(forecast, dict) else None
    if legacy:
        key = str(int(q * 100))
        return _flatten(legacy.get(key))
    return None
