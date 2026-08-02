"""MCP tool implementations that talk to the orchestrator service."""

from __future__ import annotations

from typing import Any

import httpx
import yaml

from ._orchestrator import orchestrator_client


def _strategy_payload(strategy_yaml: str) -> dict:
    return yaml.safe_load(strategy_yaml)


async def run_simulation(strategy_yaml: str) -> dict:
    """Submit one strategy YAML; returns {run_id, status}."""
    payload = _strategy_payload(strategy_yaml)
    return await orchestrator_client().post("/v1/orchestration/runs", json=payload)


async def run_simulation_batch(strategy_yamls: list[str]) -> list[dict]:
    payloads = [_strategy_payload(y) for y in strategy_yamls]
    return await orchestrator_client().post(
        "/v1/orchestration/runs/batch", json={"strategies": payloads}
    )


async def get_run_status(run_ids: list[str]) -> list[dict]:
    """Fetch status for one or more runs (one request each, returned as list)."""
    client = orchestrator_client()
    out: list[dict] = []
    for rid in run_ids:
        try:
            out.append(await client.get(f"/v1/orchestration/runs/{rid}"))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                out.append({"run_id": rid, "status": "not_found"})
                continue
            raise
    return out


async def query_results(
    experiment_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    params: dict[str, Any] = {"limit": limit}
    if experiment_id:
        params["experiment_id"] = experiment_id
    if status:
        params["status"] = status
    return await orchestrator_client().get("/v1/orchestration/runs", params=params)
