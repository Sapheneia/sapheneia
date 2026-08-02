"""Transport tests for the MCP passthrough tools.

This module previously had 0% coverage despite following the same httpx +
bearer-header pattern as its tested siblings, and it carried its own inline
model-family check that diverged from the shared enum.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from sapheneia_mcp.config import settings
from sapheneia_mcp.tools import passthroughs as pt
from shared.model_registry import UnknownModelError, require

TINY = "amazon/chronos-t5-tiny"
TINY_URL = require(TINY).base_url

ENVELOPE = {
    "model_id": TINY,
    "family": "chronos",
    "median": [1.0, 2.0],
    "quantiles": [],
    "metadata": {},
}


@pytest.fixture(autouse=True)
def _no_forecast_override(monkeypatch):
    """Default deployment resolves each model's container from the registry."""
    monkeypatch.setattr(settings, "FORECAST_URL", "")
    return monkeypatch


@respx.mock
async def test_fetch_prices_passes_params_and_request_id(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DATA_API_KEY", "dk")
    route = respx.get(f"{settings.DATA_URL}/v1/data/prices").mock(
        return_value=httpx.Response(200, json={"bars": []})
    )
    await pt.fetch_prices(
        "SPY", "2024-01-01", "2024-02-01", end_date="2024-01-10", request_id="rid-9"
    )

    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer dk"
    # The hand-rolled version never propagated a request ID at all.
    assert req.headers["X-Request-ID"] == "rid-9"
    assert dict(httpx.URL(str(req.url)).params)["end_date"] == "2024-01-10"


@respx.mock
async def test_forecast_routes_to_the_models_container() -> None:
    route = respx.post(f"{TINY_URL}/forecast/v1/chronos/forecast").mock(
        return_value=httpx.Response(200, json=ENVELOPE)
    )
    out = await pt.forecast(TINY, [1.0, 2.0], 2)

    assert out["median"] == [1.0, 2.0]
    assert json.loads(route.calls.last.request.content)["model_id"] == TINY


async def test_forecast_raises_on_an_unknown_model() -> None:
    """Must raise rather than defaulting an unrecognised id to timesfm20."""
    with pytest.raises(UnknownModelError):
        await pt.forecast("acme/mystery-model", [1.0, 2.0], 2)


@respx.mock
async def test_forecast_raises_on_upstream_5xx() -> None:
    respx.post(f"{TINY_URL}/forecast/v1/chronos/forecast").mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        await pt.forecast(TINY, [1.0, 2.0], 2)


@respx.mock
async def test_execute_trade_merges_params(monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRADING_API_KEY", "tk")
    route = respx.post(f"{settings.TRADING_URL}/trading/execute").mock(
        return_value=httpx.Response(200, json={"action": "HOLD"})
    )
    await pt.execute_trade(
        "threshold", 110.0, 100.0, 0.0, 1000.0, 1000.0, params={"threshold_value": 0.01}
    )

    body = json.loads(route.calls.last.request.content)
    assert body["threshold_value"] == 0.01
    assert body["strategy_type"] == "threshold"
    assert route.calls.last.request.headers["Authorization"] == "Bearer tk"


@respx.mock
async def test_compute_metrics_posts_returns() -> None:
    route = respx.post(f"{settings.METRICS_URL}/metrics/v1/compute").mock(
        return_value=httpx.Response(200, json={"metrics": {}})
    )
    await pt.compute_metrics([0.01, 0.02])
    assert json.loads(route.calls.last.request.content) == {
        "returns": [0.01, 0.02],
        "metric": "performance",
    }


@respx.mock
async def test_compute_metrics_raises_on_upstream_5xx() -> None:
    respx.post(f"{settings.METRICS_URL}/metrics/v1/compute").mock(return_value=httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        await pt.compute_metrics([0.0])
