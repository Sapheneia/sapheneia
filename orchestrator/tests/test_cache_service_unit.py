"""Tests for the forecast cache service.

The cache write path was silently a no-op: ``write`` looked for ``median`` at
the top level of the raw forecast response, but chronos nests it under
``prediction.median``, so ``median`` was always None and the function returned
early every time. Every run recomputed every forecast while reporting the cache
as enabled. These tests pin the write down.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from orchestrator.schemas.strategy import StrategyConfig
from orchestrator.services import cache_service
from shared.contracts import ForecastEnvelope, QuantileBand

AS_OF = datetime(2024, 3, 1, tzinfo=UTC)


def _cfg(sample_strategy, **cache) -> StrategyConfig:
    sample_strategy["cache"] = {
        "enabled": True,
        "scope": "experiment",
        "what": ["forecasts"],
        **cache,
    }
    return StrategyConfig.model_validate(sample_strategy)


def _envelope() -> ForecastEnvelope:
    return ForecastEnvelope(
        model_id="amazon/chronos-t5-tiny",
        family="chronos",
        median=[10.0, 11.0, 12.0],
        quantiles=[
            QuantileBand(quantile=0.1, values=[9.0, 10.0, 11.0]),
            QuantileBand(quantile=0.5, values=[10.0, 11.0, 12.0]),
            QuantileBand(quantile=0.9, values=[11.0, 12.0, 13.0]),
        ],
    )


async def test_write_persists_median_and_the_two_cached_quantiles(sample_strategy) -> None:
    repo = AsyncMock()
    await cache_service.write(
        repo, cfg=_cfg(sample_strategy), run_id="r1", time=AS_OF, forecast=_envelope()
    )

    repo.write.assert_awaited_once()
    kwargs = repo.write.await_args.kwargs
    assert kwargs["median"] == [10.0, 11.0, 12.0]
    assert kwargs["q10"] == [9.0, 10.0, 11.0]
    assert kwargs["q90"] == [11.0, 12.0, 13.0]
    assert kwargs["context_size"] == sample_strategy["forecast"]["context_size"]
    assert kwargs["horizon_size"] == sample_strategy["forecast"]["forecast_horizon"]


async def test_write_is_a_noop_when_cache_disabled(sample_strategy) -> None:
    repo = AsyncMock()
    await cache_service.write(
        repo,
        cfg=_cfg(sample_strategy, enabled=False),
        run_id="r1",
        time=AS_OF,
        forecast=_envelope(),
    )
    repo.write.assert_not_awaited()


async def test_write_is_a_noop_when_forecasts_not_in_what(sample_strategy) -> None:
    repo = AsyncMock()
    await cache_service.write(
        repo,
        cfg=_cfg(sample_strategy, what=[]),
        run_id="r1",
        time=AS_OF,
        forecast=_envelope(),
    )
    repo.write.assert_not_awaited()


@pytest.mark.parametrize(
    ("scope", "expected_experiment_id"),
    [("experiment", "exp-test"), ("global", None)],
)
async def test_lookup_forwards_the_configured_scope(
    sample_strategy, scope, expected_experiment_id
) -> None:
    repo = AsyncMock()
    repo.lookup.return_value = None
    await cache_service.lookup(
        repo, cfg=_cfg(sample_strategy, scope=scope), experiment_id="exp-test", time=AS_OF
    )
    assert repo.lookup.await_args.kwargs["experiment_id"] == expected_experiment_id


async def test_lookup_is_a_noop_when_cache_disabled(sample_strategy) -> None:
    repo = AsyncMock()
    result = await cache_service.lookup(
        repo, cfg=_cfg(sample_strategy, enabled=False), experiment_id="e", time=AS_OF
    )
    assert result is None
    repo.lookup.assert_not_awaited()


def test_envelope_from_row_rebuilds_bands(sample_strategy) -> None:
    cfg = _cfg(sample_strategy)
    env = cache_service.envelope_from_row(
        cfg, {"median": [1.0, 2.0], "q10": [0.5, 1.5], "q90": [1.5, 2.5]}
    )
    assert env.median == [1.0, 2.0]
    assert env.quantile(0.1) == [0.5, 1.5]
    assert env.quantile(0.9) == [1.5, 2.5]
    assert env.metadata["cache_hit"] is True


def test_envelope_from_row_tolerates_missing_bands(sample_strategy) -> None:
    env = cache_service.envelope_from_row(_cfg(sample_strategy), {"median": [1.0], "q10": None})
    assert env.quantiles == []
