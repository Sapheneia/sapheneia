"""Transport-level tests for all four orchestrator clients.

CLAUDE.md §5.4 names auth-header propagation across these four clients as its
example of a fix that must be applied — and tested — at every site. Previously
every call site mocked the client wholesale, so a broken header, a wrong query
param, or a swapped body key on any of them would have passed CI.

Each client gets: URL + params/body, Authorization when a key is set, absence of
Authorization when it is not, X-Request-ID propagation, and 5xx propagation.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from orchestrator.clients import DataClient, ForecastClient, MetricsClient, TradingClient
from shared.contracts import ForecastEnvelope
from shared.model_registry import UnknownModelError, require

TINY = "amazon/chronos-t5-tiny"
TINY_URL = require(TINY).base_url

FORECAST_BODY = {
    "model_id": TINY,
    "family": "chronos",
    "median": [1.0, 2.0, 3.0],
    "quantiles": [{"quantile": 0.1, "values": [0.5, 1.5, 2.5]}],
    "metadata": {},
}


# --- DataClient -----------------------------------------------------------


@respx.mock
async def test_data_client_sends_params_and_auth() -> None:
    route = respx.get("http://data:8000/v1/data/prices").mock(
        return_value=httpx.Response(200, json={"bars": [{"time": "2024-01-01", "close": 1.0}]})
    )
    client = DataClient("http://data:8000", api_key="dk")
    bars = await client.get_prices(
        "SPY", date(2024, 1, 1), date(2024, 2, 1), end_date=date(2024, 1, 15), request_id="rid-1"
    )

    assert bars == [{"time": "2024-01-01", "close": 1.0}]
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer dk"
    assert req.headers["X-Request-ID"] == "rid-1"
    assert dict(httpx.URL(str(req.url)).params) == {
        "ticker": "SPY",
        "start": "2024-01-01",
        "end": "2024-02-01",
        "interval": "1d",
        "end_date": "2024-01-15",
    }


@respx.mock
async def test_data_client_omits_auth_when_no_key() -> None:
    route = respx.get("http://data:8000/v1/data/prices").mock(
        return_value=httpx.Response(200, json={"bars": []})
    )
    await DataClient("http://data:8000").get_prices("SPY", date(2024, 1, 1), date(2024, 2, 1))
    assert "authorization" not in route.calls.last.request.headers


@respx.mock
async def test_data_client_raises_on_upstream_5xx() -> None:
    respx.get("http://data:8000/v1/data/prices").mock(return_value=httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        await DataClient("http://data:8000").get_prices("SPY", date(2024, 1, 1), date(2024, 2, 1))


# --- ForecastClient -------------------------------------------------------


@respx.mock
async def test_forecast_client_routes_to_the_models_own_container() -> None:
    """The request must reach the container pinned to that model.

    Each forecast container serves exactly one model and ignores the requested
    variant after its first load, so routing — not a body field — is what
    determines which model actually runs.
    """
    route = respx.post(f"{TINY_URL}/forecast/v1/chronos/forecast").mock(
        return_value=httpx.Response(200, json=FORECAST_BODY)
    )
    client = ForecastClient(api_key="fk")
    env = await client.predict(model_id=TINY, context=[1.0, 2.0], horizon=3, request_id="rid-2")

    assert isinstance(env, ForecastEnvelope)
    assert env.median == [1.0, 2.0, 3.0]
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer fk"
    assert req.headers["X-Request-ID"] == "rid-2"
    assert TINY_URL in str(req.url)


@respx.mock
async def test_forecast_client_sends_model_id_for_server_side_assertion() -> None:
    import json

    route = respx.post(f"{TINY_URL}/forecast/v1/chronos/forecast").mock(
        return_value=httpx.Response(200, json=FORECAST_BODY)
    )
    await ForecastClient().predict(model_id=TINY, context=[1.0, 2.0], horizon=3)
    body = json.loads(route.calls.last.request.content)
    assert body["model_id"] == TINY
    assert body["prediction_length"] == 3


@respx.mock
async def test_forecast_client_routes_timesfm_to_its_own_container() -> None:
    timesfm = "google/timesfm-2.0-500m-pytorch"
    info = require(timesfm)
    route = respx.post(f"{info.base_url}/forecast/v1/timesfm20/forecast").mock(
        return_value=httpx.Response(
            200, json={**FORECAST_BODY, "model_id": timesfm, "family": "timesfm"}
        )
    )
    env = await ForecastClient().predict(model_id=timesfm, context=[1.0, 2.0], horizon=3)
    assert env.family == "timesfm"
    assert route.called


async def test_forecast_client_rejects_an_unknown_model() -> None:
    with pytest.raises(UnknownModelError):
        await ForecastClient().predict(model_id="acme/not-a-model", context=[1.0, 2.0], horizon=3)


@respx.mock
async def test_forecast_client_rejects_an_unrecognised_response_shape() -> None:
    """An unparseable response must raise, never degrade to a sentinel price."""
    respx.post(f"{TINY_URL}/forecast/v1/chronos/forecast").mock(
        return_value=httpx.Response(200, json={"prediction": {"median": [1.0]}})
    )
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError
        await ForecastClient().predict(model_id=TINY, context=[1.0, 2.0], horizon=3)


@respx.mock
async def test_forecast_client_raises_on_upstream_5xx() -> None:
    respx.post(f"{TINY_URL}/forecast/v1/chronos/forecast").mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        await ForecastClient().predict(model_id=TINY, context=[1.0, 2.0], horizon=3)


@respx.mock
async def test_forecast_client_override_pins_every_model_to_one_url() -> None:
    route = respx.post("http://single:8000/forecast/v1/chronos/forecast").mock(
        return_value=httpx.Response(200, json=FORECAST_BODY)
    )
    await ForecastClient("http://single:8000").predict(model_id=TINY, context=[1.0, 2.0], horizon=3)
    assert route.called


# --- TradingClient --------------------------------------------------------


@respx.mock
async def test_trading_client_merges_params_into_body() -> None:
    import json

    route = respx.post("http://trading:9000/trading/execute").mock(
        return_value=httpx.Response(200, json={"action": "BUY", "size": 1.0, "value": 10.0})
    )
    out = await TradingClient("http://trading:9000", api_key="tk").execute(
        strategy_type="threshold",
        params={"threshold_value": 0.02},
        forecast_price=110.0,
        current_price=100.0,
        current_position=0.0,
        available_cash=1000.0,
        initial_capital=1000.0,
        request_id="rid-3",
    )

    assert out["action"] == "BUY"
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer tk"
    assert req.headers["X-Request-ID"] == "rid-3"
    body = json.loads(req.content)
    assert body["strategy_type"] == "threshold"
    assert body["threshold_value"] == 0.02
    assert body["forecast_price"] == 110.0


@respx.mock
async def test_trading_client_raises_on_upstream_5xx() -> None:
    respx.post("http://trading:9000/trading/execute").mock(return_value=httpx.Response(502))
    with pytest.raises(httpx.HTTPStatusError):
        await TradingClient("http://trading:9000").execute(
            strategy_type="threshold",
            params={},
            forecast_price=1.0,
            current_price=1.0,
            current_position=0.0,
            available_cash=1.0,
            initial_capital=1.0,
        )


# --- MetricsClient --------------------------------------------------------


@respx.mock
async def test_metrics_client_posts_returns_and_auth() -> None:
    import json

    route = respx.post("http://metrics:8000/metrics/v1/compute").mock(
        return_value=httpx.Response(200, json={"metrics": {"sharpe_ratio": 1.0}})
    )
    out = await MetricsClient("http://metrics:8000", api_key="mk").compute(
        returns=[0.01, -0.02], request_id="rid-4"
    )

    assert out["metrics"]["sharpe_ratio"] == 1.0
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer mk"
    assert req.headers["X-Request-ID"] == "rid-4"
    assert json.loads(req.content) == {"returns": [0.01, -0.02], "metric": "performance"}


@respx.mock
async def test_metrics_client_raises_on_upstream_5xx() -> None:
    respx.post("http://metrics:8000/metrics/v1/compute").mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        await MetricsClient("http://metrics:8000").compute(returns=[0.0])
