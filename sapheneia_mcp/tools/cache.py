"""Cache and run-cleanup MCP tools."""

from __future__ import annotations

from typing import Any

import httpx

from ._orchestrator import orchestrator_client, validate_run_id


async def delete_run(run_id: str) -> dict:
    try:
        return await orchestrator_client().delete(
            f"/v1/orchestration/runs/{validate_run_id(run_id)}"
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return {"deleted": False, "reason": "not_found"}
        raise


async def delete_cache(
    experiment_id: str | None = None,
    older_than_seconds: int | None = None,
) -> dict:
    params: dict[str, Any] = {}
    if experiment_id:
        params["experiment_id"] = experiment_id
    if older_than_seconds:
        params["older_than_seconds"] = older_than_seconds
    return await orchestrator_client().delete("/v1/orchestration/cache", params=params)
