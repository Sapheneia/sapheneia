"""Orchestrator REST surface."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from ..core.security import get_api_key
from ..repositories.forecasts_repo import ForecastsRepository
from ..repositories.runs_repo import RunsRepository
from ..schemas.run import (
    BatchItemResult,
    BatchSubmitRequest,
    CleanupResult,
    MetricsRow,
    RunCreated,
    RunDetail,
    RunSummary,
)
from ..services.runs_service import RunsService

router = APIRouter(prefix="/v1/orchestration", dependencies=[Depends(get_api_key)])


def _runs_service(request: Request) -> RunsService:
    svc = getattr(request.app.state, "runs_service", None)
    if svc is None:
        raise HTTPException(503, "orchestrator not initialised")
    return svc


def _runs_repo(request: Request) -> RunsRepository:
    repo = getattr(request.app.state, "runs_repo", None)
    if repo is None:
        raise HTTPException(503, "runs repository not initialised")
    return repo


def _forecasts_repo(request: Request) -> ForecastsRepository:
    repo = getattr(request.app.state, "forecasts_repo", None)
    if repo is None:
        raise HTTPException(503, "forecasts repository not initialised")
    return repo


@router.post("/runs", response_model=RunCreated)
async def submit_run(request: Request, strategy: dict[str, Any] = Body(...)) -> RunCreated:
    run_id, status = await _runs_service(request).submit(strategy)
    return RunCreated(run_id=run_id, status=status)


@router.post("/runs/batch", response_model=list[BatchItemResult])
async def submit_batch(request: Request, body: BatchSubmitRequest) -> list[BatchItemResult]:
    return await _runs_service(request).submit_batch(body.strategies)


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    request: Request,
    experiment_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    ticker: str | None = Query(default=None),
    model_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[RunSummary]:
    rows = await _runs_repo(request).list(
        experiment_id=experiment_id,
        status=status,
        ticker=ticker,
        model_id=model_id,
        limit=limit,
    )
    return [RunSummary(**_row_to_summary(r)) for r in rows]


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(request: Request, run_id: str) -> RunDetail:
    row = await _runs_repo(request).get(run_id)
    if row is None:
        raise HTTPException(404, f"run {run_id!r} not found")
    summary = _row_to_summary(row)
    metrics = MetricsRow(
        sharpe=row.get("sharpe"),
        sortino=row.get("sortino"),
        cagr=row.get("cagr"),
        calmar=row.get("calmar"),
        max_drawdown=row.get("max_drawdown"),
        win_rate=row.get("win_rate"),
        total_return=row.get("total_return"),
        extra=row.get("extra"),
    )
    return RunDetail(
        **summary,
        config=_load_json(row.get("config")),
        cache_enabled=bool(row.get("cache_enabled")),
        metrics=(
            metrics if any(getattr(metrics, k) is not None for k in metrics.model_fields) else None
        ),
    )


@router.delete("/runs/{run_id}")
async def delete_run(request: Request, run_id: str) -> dict:
    svc = _runs_service(request)
    await svc.cancel(run_id)
    deleted = await _runs_repo(request).delete(run_id)
    if deleted == 0:
        raise HTTPException(404, f"run {run_id!r} not found")
    return {"deleted": True, "run_id": run_id}


@router.delete("/cache", response_model=CleanupResult)
async def delete_cache(
    request: Request,
    experiment_id: str | None = Query(default=None),
    older_than_seconds: int | None = Query(default=None, ge=1),
) -> CleanupResult:
    if not experiment_id and not older_than_seconds:
        raise HTTPException(400, "supply experiment_id or older_than_seconds")
    repo = _forecasts_repo(request)
    deleted = 0
    if experiment_id:
        deleted += await repo.delete_by_experiment(experiment_id)
    if older_than_seconds:
        deleted += await repo.delete_older_than(older_than_seconds)
    return CleanupResult(rows_deleted=deleted)


def _row_to_summary(row: dict) -> dict:
    return {
        "run_id": row["run_id"],
        "experiment_id": row["experiment_id"],
        "ticker": row["ticker"],
        "model_id": row["model_id"],
        "strategy_type": row["strategy_type"],
        "status": row["status"],
        "started_at": row["started_at"],
        "completed_at": row.get("completed_at"),
        "error": row.get("error"),
    }


def _load_json(v):
    import json

    if isinstance(v, str):
        return json.loads(v)
    if isinstance(v, dict):
        return v
    return {}
