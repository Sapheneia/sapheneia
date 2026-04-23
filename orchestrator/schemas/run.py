"""Run-state schemas surfaced by the orchestrator API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

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
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class MetricsRow(BaseModel):
    sharpe: Optional[float] = None
    sortino: Optional[float] = None
    cagr: Optional[float] = None
    calmar: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    total_return: Optional[float] = None
    extra: Optional[dict[str, Any]] = None


class RunDetail(RunSummary):
    config: dict[str, Any]
    cache_enabled: bool
    metrics: Optional[MetricsRow] = None


class CacheLookupResult(BaseModel):
    hit: bool
    median: Optional[list[float]] = None
    q10: Optional[list[float]] = None
    q90: Optional[list[float]] = None


class CleanupResult(BaseModel):
    rows_deleted: int


class BatchSubmitRequest(BaseModel):
    strategies: list[dict[str, Any]]
