"""Shared fixtures for orchestrator tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_strategy() -> dict:
    return {
        "metadata": {
            "id": "spy-chronos-t5-tiny-threshold",
            "experiment_id": "exp-test",
            "description": "test",
            "author": "ci",
        },
        "evaluation": {
            "ticker": "SPY",
            "fetch_start_date": "2024-01-01",
            "start_date": "2024-01-15",
            "end_date": "2024-01-30",
        },
        "forecast": {
            "model": "amazon/chronos-t5-tiny",
            "context_size": 10,
            "forecast_horizon": 5,
        },
        "trading": {
            "horizon": 1,
            "initial_capital": 100_000.0,
            "initial_position": 0.0,
            "initial_cash": 100_000.0,
            "strategy_type": "threshold",
            "params": {
                "threshold_type": "absolute",
                "threshold_value": 1.0,
                "execution_size": 10.0,
            },
        },
        "metrics": ["sharpe", "max_drawdown"],
        "cache": {"enabled": False, "scope": "experiment", "what": ["forecasts"]},
    }
