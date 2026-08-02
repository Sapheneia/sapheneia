"""Unit tests for the inner loop with mocked clients and repositories."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from orchestrator.schemas.strategy import StrategyConfig
from orchestrator.services.inner_loop import InnerLoop
from shared.contracts import ForecastEnvelope, QuantileBand


def _envelope(median: list[float], **kw) -> ForecastEnvelope:
    return ForecastEnvelope(
        model_id=kw.pop("model_id", "amazon/chronos-t5-tiny"),
        family=kw.pop("family", "chronos"),
        median=median,
        **kw,
    )


def _make_inner(prices, forecast_response, trade_response, metrics_response, *, cache_hit=None):
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
    forecasts_repo.lookup.return_value = cache_hit
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
        max_per_model=3,
        # Long enough that the background heartbeat never fires during a test.
        heartbeat_interval=3600.0,
    )
    return inner, runs_repo, trades_repo, equity_repo, metrics_repo, forecasts_repo


@pytest.fixture
def synthetic_prices() -> list[dict]:
    return [
        {"time": datetime(2024, 1, 1 + i, tzinfo=UTC), "close": 100.0 + i * 0.5}
        for i in range(0, 30)
    ]


async def test_inner_loop_happy_path(sample_strategy, synthetic_prices) -> None:
    cfg = StrategyConfig.model_validate(sample_strategy)
    forecast_response = _envelope([110.0, 111.0, 112.0, 113.0, 114.0])
    trade_response = {
        "action": "BUY",
        "size": 1.0,
        "value": 110.0,
        "reason": "fcst>price",
    }
    metrics_response = {
        "sharpe_ratio": 1.5,
        "max_drawdown": -0.05,
        "cagr": 0.12,
        "calmar_ratio": 2.4,
        "win_rate": 0.6,
    }
    inner, runs_repo, trades_repo, equity_repo, metrics_repo, _ = _make_inner(
        synthetic_prices, forecast_response, trade_response, metrics_response
    )

    await inner.run("run-1", cfg, "exp-test")

    runs_repo.update_status.assert_any_await("run-1", "running")
    runs_repo.update_status.assert_any_await("run-1", "completed", completed=True, clear_error=True)
    assert trades_repo.write.await_count > 0
    assert equity_repo.write.await_count > 0
    metrics_repo.write.assert_awaited()
    args, _ = metrics_repo.write.await_args
    assert args[0] == "run-1"
    assert args[1]["sharpe"] == 1.5


async def test_inner_loop_marks_failed_on_data_error(sample_strategy) -> None:
    cfg = StrategyConfig.model_validate(sample_strategy)
    inner, runs_repo, *_ = _make_inner([], _envelope([1.0]), {}, {})

    await inner.run("run-broken", cfg, "exp-test")
    runs_repo.update_status.assert_any_await(
        "run-broken", "failed", error=AnyStringMatching(), completed=True
    )


async def test_pick_forecast_price_uses_trading_horizon(sample_strategy, synthetic_prices) -> None:
    sample_strategy["trading"]["horizon"] = 3
    cfg = StrategyConfig.model_validate(sample_strategy)
    forecast_response = _envelope([110.0, 111.0, 112.0, 113.0, 114.0])
    trade_response = {"action": "HOLD", "size": 0.0, "value": 0.0}
    metrics_response = {"sharpe_ratio": 0.0, "max_drawdown": 0.0}
    inner, *_ = _make_inner(synthetic_prices, forecast_response, trade_response, metrics_response)

    await inner.run("run-h3", cfg, "exp-test")

    _args, kwargs = inner.trading_client.execute.await_args_list[0]
    assert kwargs["forecast_price"] == 112.0  # index 2 → horizon 3


async def test_cache_hit_skips_the_forecast_service(sample_strategy, synthetic_prices) -> None:
    """A cache hit must satisfy the iteration without calling the model.

    Previously the only inner-loop test forced ``lookup`` to return None, so
    the cache-hit branch was never executed by any test.
    """
    sample_strategy["cache"] = {"enabled": True, "scope": "experiment", "what": ["forecasts"]}
    sample_strategy["trading"]["horizon"] = 2
    cfg = StrategyConfig.model_validate(sample_strategy)
    inner, *_rest, forecasts_repo = _make_inner(
        synthetic_prices,
        _envelope([999.0, 999.0, 999.0]),  # would be used only on a miss
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
        cache_hit={"median": [201.0, 202.0, 203.0], "q10": [200.0] * 3, "q90": [204.0] * 3},
    )

    await inner.run("run-cached", cfg, "exp-test")

    inner.forecast_client.predict.assert_not_awaited()
    assert forecasts_repo.lookup.await_count > 0
    _args, kwargs = inner.trading_client.execute.await_args_list[0]
    assert kwargs["forecast_price"] == 202.0  # from the cached median, horizon 2


async def test_unusable_forecast_raises_instead_of_defaulting_to_zero(
    sample_strategy, synthetic_prices
) -> None:
    """A forecast shorter than the trading horizon must fail the run.

    The old ``_pick_forecast_price`` returned 0.0 when it could not find a
    usable series. To the trading service 0.0 is not an error, it is an
    extremely strong SELL — so a bad forecast produced confident wrong trades
    and the run still finished as `completed`.
    """
    sample_strategy["trading"]["horizon"] = 5
    cfg = StrategyConfig.model_validate(sample_strategy)
    inner, runs_repo, *_ = _make_inner(
        synthetic_prices,
        _envelope([110.0]),  # only 1 step, horizon asks for 5
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-short", cfg, "exp-test")

    runs_repo.update_status.assert_any_await(
        "run-short", "failed", error=AnyStringMatching(), completed=True
    )
    inner.trading_client.execute.assert_not_awaited()


async def test_quantile_bands_survive_the_envelope(sample_strategy) -> None:
    env = _envelope(
        [1.0, 2.0],
        quantiles=[
            QuantileBand(quantile=0.1, values=[0.5, 1.5]),
            QuantileBand(quantile=0.9, values=[1.5, 2.5]),
        ],
    )
    assert env.quantile(0.1) == [0.5, 1.5]
    assert env.quantile(0.9) == [1.5, 2.5]
    assert env.quantile(0.5) is None


# --- helpers --------------------------------------------------------------


class AnyStringMatching:
    def __eq__(self, other) -> bool:
        return isinstance(other, str) and len(other) > 0
