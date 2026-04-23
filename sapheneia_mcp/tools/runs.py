"""MCP tool implementations that talk to the orchestrator service."""

from __future__ import annotations

from typing import Any, Optional

import httpx
import yaml

from ..config import settings


def _orchestrator_headers() -> dict:
    h = {}
    if settings.ORCHESTRATOR_API_KEY:
        h["Authorization"] = f"Bearer {settings.ORCHESTRATOR_API_KEY}"
    return h


def _strategy_payload(strategy_yaml: str) -> dict:
    return yaml.safe_load(strategy_yaml)


async def run_simulation(strategy_yaml: str) -> dict:
    """Submit one strategy YAML; returns {run_id, status}."""
    payload = _strategy_payload(strategy_yaml)
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        r = await client.post(
            f"{settings.ORCHESTRATOR_URL}/v1/orchestration/runs",
            json=payload,
            headers=_orchestrator_headers(),
        )
        r.raise_for_status()
        return r.json()


async def run_simulation_batch(strategy_yamls: list[str]) -> list[dict]:
    payloads = [_strategy_payload(y) for y in strategy_yamls]
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        r = await client.post(
            f"{settings.ORCHESTRATOR_URL}/v1/orchestration/runs/batch",
            json={"strategies": payloads},
            headers=_orchestrator_headers(),
        )
        r.raise_for_status()
        return r.json()


async def get_run_status(run_ids: list[str]) -> list[dict]:
    """Fetch status for one or more runs (one request each, returned as list)."""
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        for rid in run_ids:
            r = await client.get(
                f"{settings.ORCHESTRATOR_URL}/v1/orchestration/runs/{rid}",
                headers=_orchestrator_headers(),
            )
            if r.status_code == 404:
                out.append({"run_id": rid, "status": "not_found"})
                continue
            r.raise_for_status()
            out.append(r.json())
    return out


async def query_results(
    experiment_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    params: dict[str, Any] = {"limit": limit}
    if experiment_id:
        params["experiment_id"] = experiment_id
    if status:
        params["status"] = status
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        r = await client.get(
            f"{settings.ORCHESTRATOR_URL}/v1/orchestration/runs",
            params=params,
            headers=_orchestrator_headers(),
        )
        r.raise_for_status()
        return r.json()
