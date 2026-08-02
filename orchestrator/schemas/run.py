"""Run-state schemas surfaced by the orchestrator API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

#: Upper bound on a single batch submission. Matches the data service's
#: existing bound on its sibling schema. Each entry costs three DB writes and
#: an asyncio task, so an unbounded list is write amplification on one request.
MAX_BATCH_STRATEGIES = 100


class RunCreated(BaseModel):
    run_id: str
    status: str


class BatchItemResult(BaseModel):
    """One entry in a batch submission response.

    A rejected item is structurally distinguishable from an accepted one. The
    previous shape returned HTTP 200 with ``run_id="__error__"``, which the
    agent then polled and got back as ``"not_found"`` — a sentinel-on-failure of
    exactly the kind ``shared.contracts`` argues against.
    """

    index: int
    status: str  # "pending" | "rejected"
    run_id: str | None = None
    error_code: str | None = None
    error: str | None = None


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
    strategies: list[dict[str, Any]] = Field(..., min_length=1, max_length=MAX_BATCH_STRATEGIES)
