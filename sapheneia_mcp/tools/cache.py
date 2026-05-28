"""Cache and run-cleanup MCP tools."""

from __future__ import annotations

import httpx

from ..config import settings


def _headers() -> dict:
    h = {}
    if settings.ORCHESTRATOR_API_KEY:
        h["Authorization"] = f"Bearer {settings.ORCHESTRATOR_API_KEY}"
    return h


async def delete_run(run_id: str) -> dict:
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        r = await client.delete(
            f"{settings.ORCHESTRATOR_URL}/v1/orchestration/runs/{run_id}",
            headers=_headers(),
        )
        if r.status_code == 404:
            return {"deleted": False, "reason": "not_found"}
        r.raise_for_status()
        return r.json()


async def delete_cache(
    experiment_id: str | None = None,
    older_than_seconds: int | None = None,
) -> dict:
    params = {}
    if experiment_id:
        params["experiment_id"] = experiment_id
    if older_than_seconds:
        params["older_than_seconds"] = older_than_seconds
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        r = await client.delete(
            f"{settings.ORCHESTRATOR_URL}/v1/orchestration/cache",
            params=params,
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json()
