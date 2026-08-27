"""Behavioural tests for `shared.rate_limit` wiring and `shared.contracts`.

The rate-limit *values* were asserted (tests/test_rate_limit_budget.py) but the
*wiring* was not: nothing verified that `install()` actually attaches the 429
handler and middleware on the three services that gained a limiter. Likewise the
envelope's validators were only reached incidentally through the inner loop.
"""

from __future__ import annotations

import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shared.contracts import ForecastEnvelope, ForecastRequest, QuantileBand
from shared.rate_limit import install, make_limiter


def _app(limit: str) -> FastAPI:
    app = FastAPI()
    install(app, make_limiter(default_limit=limit))

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


def test_requests_under_the_cap_succeed() -> None:
    with TestClient(_app("5/minute")) as client:
        for _ in range(5):
            assert client.get("/ping").status_code == 200


def test_exceeding_the_cap_returns_429_with_the_shared_body() -> None:
    with TestClient(_app("3/minute")) as client:
        for _ in range(3):
            assert client.get("/ping").status_code == 200
        response = client.get("/ping")

    assert response.status_code == 429
    assert response.json()["error"] == "rate_limit_exceeded"


def test_a_generous_cap_does_not_throttle_a_backtest_shaped_burst() -> None:
    """The regression: a 10/minute cap made real runs die partway with a 429."""
    with TestClient(_app("6000/minute")) as client:
        codes = {client.get("/ping").status_code for _ in range(60)}
    assert codes == {200}


# --- ForecastEnvelope ------------------------------------------------------


def test_envelope_rejects_nan_in_the_median() -> None:
    """A NaN price would propagate silently into every downstream metric."""
    with pytest.raises(ValidationError):
        ForecastEnvelope(model_id="m", family="chronos", median=[1.0, math.nan])


def test_envelope_rejects_infinity_in_the_median() -> None:
    with pytest.raises(ValidationError):
        ForecastEnvelope(model_id="m", family="chronos", median=[math.inf])


def test_envelope_requires_a_non_empty_median() -> None:
    with pytest.raises(ValidationError):
        ForecastEnvelope(model_id="m", family="chronos", median=[])


@pytest.mark.parametrize("horizon", [0, -1])
def test_price_at_horizon_rejects_a_non_positive_horizon(horizon) -> None:
    env = ForecastEnvelope(model_id="m", family="chronos", median=[1.0, 2.0])
    with pytest.raises(ValueError, match="must be >= 1"):
        env.price_at_horizon(horizon)


def test_price_at_horizon_rejects_a_horizon_beyond_the_forecast() -> None:
    env = ForecastEnvelope(model_id="m", family="chronos", median=[1.0, 2.0])
    with pytest.raises(ValueError, match="exceeds forecast length"):
        env.price_at_horizon(3)


def test_price_at_horizon_is_one_indexed() -> None:
    env = ForecastEnvelope(model_id="m", family="chronos", median=[10.0, 20.0, 30.0])
    assert env.price_at_horizon(1) == 10.0
    assert env.price_at_horizon(3) == 30.0


def test_quantile_lookup_tolerates_float_representation() -> None:
    env = ForecastEnvelope(
        model_id="m",
        family="chronos",
        median=[1.0],
        quantiles=[QuantileBand(quantile=0.1, values=[0.5])],
    )
    assert env.quantile(0.1) == [0.5]
    assert env.quantile(0.2) is None


# --- ForecastRequest -------------------------------------------------------


def test_request_rejects_an_oversized_context() -> None:
    """Unbounded context would OOM a pinned single-worker model container."""
    with pytest.raises(ValidationError):
        ForecastRequest(context=[1.0] * 8193, prediction_length=1)


def test_request_rejects_too_short_a_context() -> None:
    with pytest.raises(ValidationError):
        ForecastRequest(context=[1.0], prediction_length=1)


def test_request_accepts_a_realistic_backtest_context() -> None:
    request = ForecastRequest(context=[1.0] * 252, prediction_length=20)
    assert request.num_samples == 20
    assert request.model_id is None


# --- history contract floor -------------------------------------------------


def test_trading_array_limit_defaults_to_the_shared_contract_floor() -> None:
    """One constant, two readers: the orchestrator caps its assembly at
    MAX_HISTORY_BARS and the trading schema rejects beyond MAX_ARRAY_SIZE.
    If the default ever diverges from the contract floor, the sender can
    build requests the receiver rejects."""
    from shared.contracts import MAX_HISTORY_BARS
    from trading.core.config import TradingSettings

    assert TradingSettings(_env_file=None).MAX_ARRAY_SIZE == MAX_HISTORY_BARS
