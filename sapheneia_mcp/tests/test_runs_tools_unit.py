"""Unit tests for the orchestrator-facing MCP tools (mocked HTTP)."""

from __future__ import annotations

import respx
from httpx import Response

from sapheneia_mcp.config import settings
from sapheneia_mcp.tools import cache as cache_tools
from sapheneia_mcp.tools import runs as run_tools


SAMPLE_STRATEGY_YAML = """\
metadata:
  id: spy-test
  experiment_id: exp-test
  description: ""
  author: ""

evaluation:
  ticker: SPY
  fetch_start_date: "20211201"
  start_date: "20230101"
  end_date: "20240101"

forecast:
  model: amazon/chronos-t5-tiny
  context_size: 252
  forecast_horizon: 20

trading:
  horizon: 1
  initial_capital: 100000.0
  initial_position: 0.0
  initial_cash: 100000.0
  strategy_type: threshold
  params: {threshold_type: absolute, threshold_value: 1.0, execution_size: 10.0}

metrics: [sharpe]
cache: {enabled: false, scope: experiment, what: [forecasts]}
"""


@respx.mock
async def test_run_simulation_posts_to_orchestrator() -> None:
    route = respx.post(f"{settings.ORCHESTRATOR_URL}/v1/orchestration/runs").mock(
        return_value=Response(200, json={"run_id": "run-123", "status": "pending"})
    )
    result = await run_tools.run_simulation(SAMPLE_STRATEGY_YAML)
    assert result == {"run_id": "run-123", "status": "pending"}
    assert route.called


@respx.mock
async def test_run_simulation_batch_posts_payloads() -> None:
    route = respx.post(f"{settings.ORCHESTRATOR_URL}/v1/orchestration/runs/batch").mock(
        return_value=Response(
            200,
            json=[
                {"run_id": "r1", "status": "pending"},
                {"run_id": "r2", "status": "pending"},
            ],
        )
    )
    result = await run_tools.run_simulation_batch([SAMPLE_STRATEGY_YAML, SAMPLE_STRATEGY_YAML])
    assert len(result) == 2
    assert route.called


@respx.mock
async def test_get_run_status_handles_404() -> None:
    respx.get(f"{settings.ORCHESTRATOR_URL}/v1/orchestration/runs/missing").mock(
        return_value=Response(404, json={"error": "not_found"})
    )
    result = await run_tools.get_run_status(["missing"])
    assert result == [{"run_id": "missing", "status": "not_found"}]


@respx.mock
async def test_query_results_passes_filters() -> None:
    route = respx.get(f"{settings.ORCHESTRATOR_URL}/v1/orchestration/runs").mock(
        return_value=Response(200, json=[])
    )
    await run_tools.query_results(experiment_id="exp-test", status="completed", limit=50)
    assert route.called
    sent = route.calls[0].request.url.params
    assert sent["experiment_id"] == "exp-test"
    assert sent["status"] == "completed"
    assert sent["limit"] == "50"


@respx.mock
async def test_delete_cache_requires_at_least_one_filter() -> None:
    route = respx.delete(f"{settings.ORCHESTRATOR_URL}/v1/orchestration/cache").mock(
        return_value=Response(200, json={"rows_deleted": 5})
    )
    out = await cache_tools.delete_cache(experiment_id="exp-test")
    assert out == {"rows_deleted": 5}
    assert route.called
