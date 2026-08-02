"""The intra-cluster hot paths must not be rate-limited below their workload.

The orchestrator's inner loop makes one forecast call and one trading call per
backtest iteration — one per trading day. With the original 10/minute caps on
``/trading/execute`` and the forecast inference endpoints, a real backtest was
impossible: every run died partway through with a 429 from an internal caller.

These limits are per-client-IP and all orchestrator traffic arrives from a
single container IP, so the whole run shares one bucket. That makes the budget
below the correct thing to assert.
"""

from __future__ import annotations

import pytest

#: A year of daily bars. The example strategy evaluates ~2 months; a 10-year
#: sweep is ~2,520. One minute of sustained iteration must not trip the limiter.
ITERATIONS_PER_YEAR = 252

#: Headroom for concurrent runs sharing one per-IP bucket
#: (ORCHESTRATOR_MAX_CONCURRENT_RUNS defaults to 4).
CONCURRENT_RUNS = 4

MIN_HOT_PATH_BUDGET = ITERATIONS_PER_YEAR * CONCURRENT_RUNS


def test_trading_execute_limit_supports_a_real_backtest() -> None:
    from trading.core.config import settings

    assert settings.RATE_LIMIT_EXECUTE_PER_MINUTE >= MIN_HOT_PATH_BUDGET, (
        "trading /execute is rate-limited below what one backtest needs; "
        "the orchestrator calls it once per trading day"
    )


def test_trading_default_limit_is_not_the_binding_constraint() -> None:
    from trading.core.config import settings

    assert settings.RATE_LIMIT_PER_MINUTE >= 600


def test_forecast_inference_limit_supports_a_real_backtest() -> None:
    forecast_config = pytest.importorskip("forecast.core.config")

    assert forecast_config.settings.RATE_LIMIT_INFERENCE_PER_MINUTE >= 600, (
        "forecast inference is rate-limited below what one backtest needs"
    )
    # The canonical /forecast endpoint uses the "default" bucket.
    assert forecast_config.settings.RATE_LIMIT_PER_MINUTE >= 600


def test_orchestrator_limit_supports_agent_polling() -> None:
    from orchestrator.core.config import settings

    # The agent polls every in-flight run; with 4 concurrent runs on a 2s
    # interval that is 120 req/min before any submissions.
    assert settings.RATE_LIMIT_PER_MINUTE >= 600
