"""Run-state schemas surfaced by the orchestrator API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RunCreated(BaseModel):
    run_id: str
    status: str


class RunSummary(BaseModel):
    run_id: str
    experiment_id: str
    ticker: str
    model_id: str
    strategy_type: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class MetricsRow(BaseModel):
    sharpe: float | None = None
    sortino: float | None = None
    cagr: float | None = None
    calmar: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None
    total_return: float | None = None
    extra: dict[str, Any] | None = None


class RunDetail(RunSummary):
    config: dict[str, Any]
    cache_enabled: bool
    metrics: MetricsRow | None = None


class CacheLookupResult(BaseModel):
    hit: bool
    median: list[float] | None = None
    q10: list[float] | None = None
    q90: list[float] | None = None


class CleanupResult(BaseModel):
    rows_deleted: int


class BatchSubmitRequest(BaseModel):
    strategies: list[dict[str, Any]]
