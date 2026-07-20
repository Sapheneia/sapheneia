"""Schema validation tests for StrategyConfig."""

from __future__ import annotations

import pytest

from orchestrator.schemas.strategy import StrategyConfig


def test_valid_strategy(sample_strategy: dict) -> None:
    cfg = StrategyConfig.model_validate(sample_strategy)
    assert cfg.evaluation.ticker == "SPY"
    assert cfg.forecast.context_size == 10
    assert cfg.trading.horizon == 1


def test_trading_horizon_must_not_exceed_forecast_horizon(
    sample_strategy: dict,
) -> None:
    sample_strategy["trading"]["horizon"] = 99  # > forecast_horizon 5
    with pytest.raises(Exception):
        StrategyConfig.model_validate(sample_strategy)


@pytest.mark.parametrize("date_str", ["2024-01-15", "20240115"])
def test_parse_date_accepts_two_formats(sample_strategy: dict, date_str: str) -> None:
    sample_strategy["evaluation"]["start_date"] = date_str
    cfg = StrategyConfig.model_validate(sample_strategy)
    assert cfg.evaluation.parse_date("start_date").year == 2024


def test_invalid_strategy_type_rejected(sample_strategy: dict) -> None:
    sample_strategy["trading"]["strategy_type"] = "bogus"
    with pytest.raises(Exception):
        StrategyConfig.model_validate(sample_strategy)


def test_default_cache_disabled(sample_strategy: dict) -> None:
    cfg = StrategyConfig.model_validate(sample_strategy)
    assert cfg.cache.enabled is False
    assert cfg.cache.scope == "experiment"
