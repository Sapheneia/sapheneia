"""Unit tests for the inner loop with mocked clients and repositories."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


@pytest.fixture
def synthetic_ohlc_prices() -> list[dict]:
    """Thirty daily bars with distinct, per-field-derivable OHLC values."""
    bars = []
    for i in range(0, 30):
        base = 100.0 + i * 0.5
        bars.append(
            {
                "time": datetime(2024, 1, 1 + i, tzinfo=UTC),
                "open": base - 1.0,
                "high": base + 2.0,
                "low": base - 2.0,
                "close": base,
            }
        )
    return bars


def _quantile_strategy(sample_strategy: dict, window_history: int = 5) -> dict:
    sample_strategy["trading"]["strategy_type"] = "quantile"
    sample_strategy["trading"]["params"] = {
        "which_history": "close",
        "window_history": window_history,
        "quantile_signals": {
            0: {"range": [0, 25], "signal": "buy", "multiplier": 1.0},
            1: {"range": [25, 75], "signal": "hold", "multiplier": 0.0},
            2: {"range": [75, 100], "signal": "sell", "multiplier": 1.0},
        },
    }
    return sample_strategy


async def test_quantile_strategy_receives_ohlc_history(
    sample_strategy, synthetic_ohlc_prices
) -> None:
    """The orchestrator must assemble the OHLC arrays the quantile schema requires.

    The trading service is pure compute and cannot fetch bars itself; before
    this assembly existed every quantile request 422'd on the four required
    ``*_history`` fields while threshold requests sailed through.
    """
    window = 5
    cfg = StrategyConfig.model_validate(_quantile_strategy(sample_strategy, window))
    inner, runs_repo, trades_repo, *_ = _make_inner(
        synthetic_ohlc_prices,
        _envelope([110.0, 111.0, 112.0, 113.0, 114.0]),
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-quantile", cfg, "exp-test")

    runs_repo.update_status.assert_any_await(
        "run-quantile", "completed", completed=True, clear_error=True
    )
    calls = inner.trading_client.execute.await_args_list
    # Eval window is Jan 15..30 inclusive: one trade call per bar.
    assert len(calls) == 16

    def expected(field: str, as_of_index: int) -> list[float]:
        return [
            float(synthetic_ohlc_prices[i][field])
            for i in range(as_of_index - window + 1, as_of_index + 1)
        ]

    # First call trades on Jan 15 (index 14); last on Jan 30 (index 29).
    for call, as_of_index in ((calls[0], 14), (calls[-1], 29)):
        params = call.kwargs["params"]
        for field in ("open", "high", "low", "close"):
            history = params[f"{field}_history"]
            # Correct window: exactly window_history bars, the exact synthetic
            # values ending at as_of — exact equality also proves no future bar
            # leaked in.
            assert len(history) == window
            assert history == expected(field, as_of_index)
        # Belt and braces on look-ahead: nothing beyond the as_of bar's value.
        assert max(params["close_history"]) == synthetic_ohlc_prices[as_of_index]["close"]
        # Config params ride along untouched next to the runtime arrays.
        assert params["which_history"] == "close"
        assert params["window_history"] == window
        assert set(params["quantile_signals"]) == {0, 1, 2}

    # The config dict itself must not be polluted with runtime market data.
    assert "open_history" not in cfg.trading.params


async def test_quantile_without_window_history_fails_loudly(
    sample_strategy, synthetic_ohlc_prices
) -> None:
    """A missing window_history must fail the run with a pointed message.

    ``bars[-0:]`` would otherwise silently ship the entire price history to a
    request the trading schema rejects anyway.
    """
    strategy = _quantile_strategy(sample_strategy)
    del strategy["trading"]["params"]["window_history"]
    cfg = StrategyConfig.model_validate(strategy)
    inner, runs_repo, *_ = _make_inner(
        synthetic_ohlc_prices,
        _envelope([110.0]),
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-no-window", cfg, "exp-test")

    _args, kwargs = runs_repo.update_status.await_args_list[-1]
    assert _args[:2] == ("run-no-window", "failed")
    assert "window_history" in kwargs["error"]
    inner.trading_client.execute.assert_not_awaited()
    # The check is hoisted: a misconfigured run must fail before paying a
    # price fetch or a forecast round-trip.
    inner.data_client.get_prices.assert_not_awaited()
    inner.forecast_client.predict.assert_not_awaited()


async def test_quantile_with_close_only_data_fails_loudly(sample_strategy) -> None:
    """A price source with no usable OHLC bars must fail the run.

    The quantile schema accepts empty arrays and the trading service then holds
    every iteration — the run would "complete" with a flat equity curve and
    meaningless metrics. Silently-wrong is worse than failing.
    """
    close_only = [
        {"time": datetime(2024, 1, 1 + i, tzinfo=UTC), "close": 100.0 + i * 0.5}
        for i in range(0, 30)
    ]
    cfg = StrategyConfig.model_validate(_quantile_strategy(sample_strategy))
    inner, runs_repo, *_ = _make_inner(
        close_only,
        _envelope([110.0]),
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-close-only", cfg, "exp-test")

    _args, kwargs = runs_repo.update_status.await_args_list[-1]
    assert _args[:2] == ("run-close-only", "failed")
    assert "OHLC" in kwargs["error"]
    inner.trading_client.execute.assert_not_awaited()


async def test_atr_threshold_receives_ohlc_history(sample_strategy, synthetic_ohlc_prices) -> None:
    """Same bug class as quantile, same fix, same test shape (§5.4).

    ThresholdStrategyRequest's validate_atr_requirements rejects
    threshold_type="atr" without all four OHLC arrays, so an ATR run 422'd on
    every iteration exactly as quantile did.
    """
    window = 5
    sample_strategy["trading"]["params"] = {
        "threshold_type": "atr",
        "threshold_value": 2.0,
        "window_history": window,
    }
    cfg = StrategyConfig.model_validate(sample_strategy)
    inner, runs_repo, *_ = _make_inner(
        synthetic_ohlc_prices,
        _envelope([110.0]),
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-atr", cfg, "exp-test")

    runs_repo.update_status.assert_any_await(
        "run-atr", "completed", completed=True, clear_error=True
    )
    params = inner.trading_client.execute.await_args_list[0].kwargs["params"]
    for field in ("open", "high", "low", "close"):
        history = params[f"{field}_history"]
        assert len(history) == window
        # First call trades on Jan 15 (index 14): exact slice, no future bars.
        assert history == [float(synthetic_ohlc_prices[i][field]) for i in range(10, 15)]
    assert params["threshold_type"] == "atr"


async def test_atr_threshold_without_window_sends_full_history(
    sample_strategy, synthetic_ohlc_prices
) -> None:
    """window_history is optional for threshold — the service defaults it.

    Rather than duplicating the trading service's default window constant
    (§3.5 drift), the orchestrator sends every usable bar up to as_of and the
    service applies its own ``[-window_history:]`` slice.
    """
    sample_strategy["trading"]["params"] = {"threshold_type": "atr", "threshold_value": 2.0}
    cfg = StrategyConfig.model_validate(sample_strategy)
    inner, *_ = _make_inner(
        synthetic_ohlc_prices,
        _envelope([110.0]),
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-atr-default", cfg, "exp-test")

    calls = inner.trading_client.execute.await_args_list
    # First call: all 15 bars up to Jan 15; last call: all 30 bars up to Jan 30.
    assert len(calls[0].kwargs["params"]["close_history"]) == 15
    assert len(calls[-1].kwargs["params"]["close_history"]) == 30


async def test_normalized_return_receives_history(sample_strategy, synthetic_ohlc_prices) -> None:
    """ReturnStrategyRequest requires history when position_sizing="normalized" (§5.4)."""
    window = 5
    sample_strategy["trading"]["params"] = {
        "position_sizing": "normalized",
        "threshold_value": 0.05,
        "which_history": "close",
        "window_history": window,
    }
    sample_strategy["trading"]["strategy_type"] = "return"
    cfg = StrategyConfig.model_validate(sample_strategy)
    inner, runs_repo, *_ = _make_inner(
        synthetic_ohlc_prices,
        _envelope([110.0]),
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-normalized", cfg, "exp-test")

    runs_repo.update_status.assert_any_await(
        "run-normalized", "completed", completed=True, clear_error=True
    )
    params = inner.trading_client.execute.await_args_list[0].kwargs["params"]
    assert params["close_history"] == [
        float(synthetic_ohlc_prices[i]["close"]) for i in range(10, 15)
    ]
    assert params["position_sizing"] == "normalized"


async def test_plain_threshold_params_forwarded_verbatim(
    sample_strategy, synthetic_ohlc_prices
) -> None:
    """Variants that need no history must keep getting config params untouched."""
    cfg = StrategyConfig.model_validate(sample_strategy)  # percentage-free threshold config
    inner, *_ = _make_inner(
        synthetic_ohlc_prices,
        _envelope([110.0]),
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-plain", cfg, "exp-test")

    params = inner.trading_client.execute.await_args_list[0].kwargs["params"]
    assert params == cfg.trading.params
    assert not any(key.endswith("_history") for key in params)


async def test_std_dev_threshold_receives_ohlc_history(
    sample_strategy, synthetic_ohlc_prices
) -> None:
    """std_dev is the silent sibling: without history the trading service falls
    back to treating threshold_value as an ABSOLUTE dollar threshold with only a
    warning — no 422, just wrong numbers. The assembly must cover it (§5.4).
    """
    window = 5
    sample_strategy["trading"]["params"] = {
        "threshold_type": "std_dev",
        "threshold_value": 2.0,
        "which_history": "close",
        "window_history": window,
    }
    cfg = StrategyConfig.model_validate(sample_strategy)
    inner, runs_repo, *_ = _make_inner(
        synthetic_ohlc_prices,
        _envelope([110.0]),
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-stddev", cfg, "exp-test")

    runs_repo.update_status.assert_any_await(
        "run-stddev", "completed", completed=True, clear_error=True
    )
    params = inner.trading_client.execute.await_args_list[0].kwargs["params"]
    assert params["close_history"] == [
        float(synthetic_ohlc_prices[i]["close"]) for i in range(10, 15)
    ]
    assert len(params["open_history"]) == window


async def test_config_embedded_history_is_rejected(sample_strategy, synthetic_ohlc_prices) -> None:
    """Static history arrays in config would be silently overwritten — fail loudly.

    Before the assembly existed such a config could pass the trading schema and
    "work"; overwriting it without a trace would change its numbers silently.
    """
    strategy = _quantile_strategy(sample_strategy)
    strategy["trading"]["params"]["close_history"] = [1.0, 2.0, 3.0]
    cfg = StrategyConfig.model_validate(strategy)
    inner, runs_repo, *_ = _make_inner(
        synthetic_ohlc_prices,
        _envelope([110.0]),
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-embedded", cfg, "exp-test")

    _args, kwargs = runs_repo.update_status.await_args_list[-1]
    assert _args[:2] == ("run-embedded", "failed")
    assert "close_history" in kwargs["error"]
    inner.trading_client.execute.assert_not_awaited()


async def test_no_window_send_is_capped_at_the_contract_floor(sample_strategy) -> None:
    """The sender must never build a request the receiver rejects (ASVS 4.2.5).

    The trading schema rejects history arrays longer than the shared
    MAX_HISTORY_BARS, so the send-everything path (window_history unset) caps
    what it assembles at the same constant instead of 422ing on pathological
    fetch windows (>10k daily bars is ~40 years).
    """
    from shared.contracts import MAX_HISTORY_BARS

    many_bars = [
        {
            "time": datetime(2000, 1, 1, tzinfo=UTC) + timedelta(days=i),
            "open": 99.0,
            "high": 101.0,
            "low": 98.0,
            "close": 100.0,
        }
        for i in range(MAX_HISTORY_BARS + 50)
    ]
    sample_strategy["evaluation"]["fetch_start_date"] = "2000-01-01"
    sample_strategy["evaluation"]["start_date"] = "2027-06-01"
    sample_strategy["evaluation"]["end_date"] = "2027-06-30"
    sample_strategy["trading"]["params"] = {"threshold_type": "atr", "threshold_value": 2.0}
    cfg = StrategyConfig.model_validate(sample_strategy)
    inner, *_ = _make_inner(
        many_bars,
        _envelope([110.0]),
        {"action": "HOLD", "size": 0.0, "value": 0.0},
        {"sharpe_ratio": 0.0},
    )

    await inner.run("run-cap", cfg, "exp-test")

    calls = inner.trading_client.execute.await_args_list
    assert calls, "no trade calls made"
    last = calls[-1].kwargs["params"]
    assert len(last["close_history"]) == MAX_HISTORY_BARS


# --- helpers --------------------------------------------------------------


class AnyStringMatching:
    def __eq__(self, other) -> bool:
        return isinstance(other, str) and len(other) > 0
