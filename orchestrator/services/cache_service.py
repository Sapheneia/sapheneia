"""Forecast-cache lookup and write, scope-aware.

Now that both forecast families return a validated ``ForecastEnvelope``, this
module reads one shape instead of guessing between three.

That guessing was not harmless. The previous ``write`` looked for ``median`` at
the top level of the raw response, but chronos nests it under
``prediction.median`` — so ``median`` was always ``None``, ``write`` returned
early every time, and the forecast cache silently never populated. Every run
recomputed every forecast while reporting cache-enabled.
"""

from __future__ import annotations

from datetime import datetime

from shared.contracts import ForecastEnvelope, QuantileBand

from ..repositories.forecasts_repo import ForecastsRepository
from ..schemas.strategy import StrategyConfig

#: Quantile bands persisted alongside the median.
CACHED_QUANTILES = (0.1, 0.9)


def _enabled(cfg: StrategyConfig) -> bool:
    return bool(cfg.cache.enabled) and "forecasts" in cfg.cache.what


async def lookup(
    repo: ForecastsRepository,
    *,
    cfg: StrategyConfig,
    experiment_id: str,
    time: datetime,
) -> dict | None:
    if not _enabled(cfg):
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
    forecast: ForecastEnvelope,
) -> None:
    if not _enabled(cfg):
        return
    if not forecast.median:
        return
    q10 = forecast.quantile(0.1)
    q90 = forecast.quantile(0.9)
    await repo.write(
        run_id=run_id,
        ticker=cfg.evaluation.ticker,
        time=time,
        model_id=cfg.forecast.model,
        context_size=cfg.forecast.context_size,
        horizon_size=cfg.forecast.forecast_horizon,
        median=list(forecast.median),
        q10=list(q10) if q10 is not None else None,
        q90=list(q90) if q90 is not None else None,
    )


def envelope_from_row(cfg: StrategyConfig, row: dict) -> ForecastEnvelope:
    """Rebuild an envelope from a cache hit so callers see one type."""
    bands = []
    for q, key in ((0.1, "q10"), (0.9, "q90")):
        values = row.get(key)
        if values:
            bands.append(QuantileBand(quantile=q, values=[float(v) for v in values]))
    return ForecastEnvelope(
        model_id=cfg.forecast.model,
        family=str(row.get("family") or ""),
        median=[float(v) for v in row["median"]],
        quantiles=bands,
        metadata={"cache_hit": True},
    )
