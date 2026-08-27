"""Endpoint unit tests with the orchestrator wired against fakes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator.main import app
from orchestrator.schemas.run import BatchItemResult


# Replace the real lifespan (which would try to connect to TimescaleDB) with a no-op.
# Tests inject their own fakes into app.state directly.
@asynccontextmanager
async def _noop_lifespan(_app: FastAPI):
    yield


app.router.lifespan_context = _noop_lifespan


@pytest.fixture
def wired_app(sample_strategy: dict):
    runs_service = AsyncMock()
    runs_service.submit.return_value = ("run-xyz", "pending")
    runs_service.submit_batch.return_value = [
        BatchItemResult(index=0, status="pending", run_id="run-1"),
        BatchItemResult(index=1, status="rejected", error_code="INVALID_MODEL", error="nope"),
    ]
    runs_service.cancel.return_value = True

    runs_repo = AsyncMock()
    runs_repo.list.return_value = [
        {
            "run_id": "run-xyz",
            "experiment_id": "exp-test",
            "ticker": "SPY",
            "model_id": "amazon/chronos-t5-tiny",
            "strategy_type": "threshold",
            "status": "completed",
            "started_at": datetime(2024, 1, 1, 12, 0, 0),
            "completed_at": datetime(2024, 1, 1, 12, 5, 0),
            "error": None,
        }
    ]
    runs_repo.get.return_value = {
        "run_id": "run-xyz",
        "experiment_id": "exp-test",
        "ticker": "SPY",
        "model_id": "amazon/chronos-t5-tiny",
        "strategy_type": "threshold",
        "status": "completed",
        "started_at": datetime(2024, 1, 1, 12, 0, 0),
        "completed_at": datetime(2024, 1, 1, 12, 5, 0),
        "error": None,
        "config": "{}",
        "cache_enabled": False,
        "sharpe": 1.2,
        "sortino": None,
        "cagr": None,
        "calmar": None,
        "max_drawdown": -0.1,
        "win_rate": None,
        "total_return": None,
        "extra": None,
    }
    runs_repo.delete.return_value = 1

    forecasts_repo = AsyncMock()
    forecasts_repo.delete_by_experiment.return_value = 5
    forecasts_repo.delete_older_than.return_value = 0

    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value.fetchval = AsyncMock(return_value=1)

    app.state.runs_service = runs_service
    app.state.runs_repo = runs_repo
    app.state.forecasts_repo = forecasts_repo
    app.state.pool = pool

    yield app

    for attr in ("runs_service", "runs_repo", "forecasts_repo", "pool"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)


def test_health_ok(wired_app):
    with TestClient(wired_app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["db"] is True


def test_submit_run(wired_app, sample_strategy):
    with TestClient(wired_app) as client:
        r = client.post("/v1/orchestration/runs", json=sample_strategy)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_id"] == "run-xyz"
    assert body["status"] == "pending"


def test_submit_batch(wired_app, sample_strategy):
    with TestClient(wired_app) as client:
        r = client.post(
            "/v1/orchestration/runs/batch",
            json={"strategies": [sample_strategy, sample_strategy]},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 2
    # A rejected item is structurally distinguishable, not a sentinel run_id.
    assert body[0]["run_id"] == "run-1" and body[0]["status"] == "pending"
    assert body[1]["run_id"] is None
    assert body[1]["status"] == "rejected"
    assert body[1]["error_code"] == "INVALID_MODEL"


def test_list_runs(wired_app):
    with TestClient(wired_app) as client:
        r = client.get("/v1/orchestration/runs", params={"experiment_id": "exp-test"})
    assert r.status_code == 200
    assert r.json()[0]["run_id"] == "run-xyz"


def test_get_run_with_metrics(wired_app):
    with TestClient(wired_app) as client:
        r = client.get("/v1/orchestration/runs/run-xyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["metrics"]["sharpe"] == 1.2


def test_delete_run(wired_app):
    with TestClient(wired_app) as client:
        r = client.delete("/v1/orchestration/runs/run-xyz")
    assert r.status_code == 200
    assert r.json()["deleted"] is True


def test_delete_cache_requires_filter(wired_app):
    with TestClient(wired_app) as client:
        r = client.delete("/v1/orchestration/cache")
    assert r.status_code == 400


def test_delete_cache_by_experiment(wired_app):
    with TestClient(wired_app) as client:
        r = client.delete("/v1/orchestration/cache", params={"experiment_id": "exp-test"})
    assert r.status_code == 200
    assert r.json()["rows_deleted"] == 5
