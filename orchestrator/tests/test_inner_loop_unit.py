"""Unit tests for the inner loop with mocked clients and repositories."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from orchestrator.schemas.strategy import StrategyConfig
from orchestrator.services.inner_loop import InnerLoop


def _make_inner(prices, forecast_response, trade_response, metrics_response):
    data_client = AsyncMock()
    data_client.get_prices.return_value = prices

    forecast_client = AsyncMock()
    forecast_client.predict.return_value = forecast_response

    trading_client = AsyncMock()
    trading_client.execute.return_value = trade_response

    metrics_client = AsyncMock()
    metrics_client.compute.return_value = metrics_response

    runs_repo = AsyncMock()
    forecasts_repo = AsyncMock()
    forecasts_repo.lookup.return_value = None  # always cache-miss
    trades_repo = AsyncMock()
    equity_repo = AsyncMock()
    metrics_repo = AsyncMock()

    inner = InnerLoop(
        data_client=data_client,
        forecast_client=forecast_client,
        trading_client=trading_client,
        metrics_client=metrics_client,
        runs_repo=runs_repo,
        forecasts_repo=forecasts_repo,
        trades_repo=trades_repo,
        equity_repo=equity_repo,
        metrics_repo=metrics_repo,
        per_model_semaphores={},
    )
    return inner, runs_repo, trades_repo, equity_repo, metrics_repo


@pytest.fixture
def synthetic_prices() -> list[dict]:
    return [{"time": datetime(2024, 1, 1 + i), "close": 100.0 + i * 0.5} for i in range(0, 30)]


async def test_inner_loop_happy_path(sample_strategy, synthetic_prices) -> None:
    cfg = StrategyConfig.model_validate(sample_strategy)
    forecast_response = {"median": [110.0, 111.0, 112.0, 113.0, 114.0]}
    trade_response = {"action": "BUY", "size": 1.0, "value": 110.0, "reason": "fcst>price"}
    metrics_response = {
        "sharpe_ratio": 1.5,
        "max_drawdown": -0.05,
        "cagr": 0.12,
        "calmar_ratio": 2.4,
        "win_rate": 0.6,
    }
    inner, runs_repo, trades_repo, equity_repo, metrics_repo = _make_inner(
        synthetic_prices, forecast_response, trade_response, metrics_response
    )

    await inner.run("run-1", cfg, "exp-test")

    runs_repo.update_status.assert_any_await("run-1", "running")
    runs_repo.update_status.assert_any_await("run-1", "completed", completed=True)
    assert trades_repo.write.await_count > 0
    assert equity_repo.write.await_count > 0
    metrics_repo.write.assert_awaited()
    args, _ = metrics_repo.write.await_args
    assert args[0] == "run-1"
    assert args[1]["sharpe"] == 1.5


async def test_inner_loop_marks_failed_on_data_error(sample_strategy) -> None:
    cfg = StrategyConfig.model_validate(sample_strategy)
    inner, runs_repo, *_ = _make_inner([], {}, {}, {})

    await inner.run("run-broken", cfg, "exp-test")
    runs_repo.update_status.assert_any_await(
        "run-broken", "failed", error=AnyStringMatching(), completed=True
    )


async def test_pick_forecast_price_uses_trading_horizon(sample_strategy, synthetic_prices) -> None:
    sample_strategy["trading"]["horizon"] = 3
    cfg = StrategyConfig.model_validate(sample_strategy)
    forecast_response = {"median": [110.0, 111.0, 112.0, 113.0, 114.0]}
    trade_response = {"action": "HOLD", "size": 0.0, "value": 0.0}
    metrics_response = {"sharpe_ratio": 0.0, "max_drawdown": 0.0}
    inner, _runs, _trades, _eq, _metrics = _make_inner(
        synthetic_prices, forecast_response, trade_response, metrics_response
    )

    await inner.run("run-h3", cfg, "exp-test")

    args, kwargs = inner.trading_client.execute.await_args_list[0]
    assert kwargs["forecast_price"] == 112.0  # index 2 → horizon 3


# --- helpers --------------------------------------------------------------


class AnyStringMatching:
    def __eq__(self, other) -> bool:
        return isinstance(other, str) and len(other) > 0
