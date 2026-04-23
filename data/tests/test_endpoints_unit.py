"""Unit tests for the data service endpoints (no DB, mocked repo)."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from data.core.config import settings
from data.main import app
from data.tests.conftest import FakeRecord


@pytest.fixture
def fake_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.read_through.return_value = [
        FakeRecord(
            time=datetime(2024, 1, 2),
            ticker="SPY",
            open=470.0,
            high=472.0,
            low=468.5,
            close=471.5,
            adj_close=471.5,
            volume=80_000_000,
        )
    ]
    repo.read_many.return_value = {"SPY": repo.read_through.return_value}
    return repo


@pytest.fixture
def client(fake_repo: AsyncMock):
    settings.API_KEY = ""  # disable auth for unit tests
    app.state.prices_repo = fake_repo
    app.state.pool = AsyncMock()
    with TestClient(app) as c:
        yield c
    delattr(app.state, "prices_repo")


def test_health_returns_ok(client: TestClient) -> None:
    fake_pool = app.state.pool
    fake_conn = AsyncMock()
    fake_conn.fetchval.return_value = 1
    fake_pool.acquire.return_value.__aenter__.return_value = fake_conn

    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] is True


def test_get_prices_happy_path(client: TestClient, fake_repo: AsyncMock) -> None:
    r = client.get(
        "/v1/data/prices",
        params={"ticker": "SPY", "start": "2024-01-01", "end": "2024-01-31"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ticker"] == "SPY"
    assert body["interval"] == "1d"
    assert len(body["bars"]) == 1
    assert body["bars"][0]["close"] == 471.5
    fake_repo.read_through.assert_awaited_once()


def test_get_prices_rejects_inverted_range(client: TestClient) -> None:
    r = client.get(
        "/v1/data/prices",
        params={"ticker": "SPY", "start": "2024-02-01", "end": "2024-01-01"},
    )
    assert r.status_code == 400


def test_get_prices_propagates_end_date_for_temporal_isolation(
    client: TestClient, fake_repo: AsyncMock
) -> None:
    r = client.get(
        "/v1/data/prices",
        params={
            "ticker": "SPY",
            "start": "2024-01-01",
            "end": "2024-12-31",
            "end_date": "2024-06-30",
        },
    )
    assert r.status_code == 200
    args, kwargs = fake_repo.read_through.call_args
    assert kwargs.get("end_date") == date(2024, 6, 30) or args[-1] == date(2024, 6, 30)


def test_fetch_endpoint_invokes_read_many(client: TestClient, fake_repo: AsyncMock) -> None:
    r = client.post(
        "/v1/data/fetch",
        json={
            "tickers": ["SPY", "QQQ"],
            "start": "2024-01-01",
            "end": "2024-01-31",
            "interval": "1d",
        },
    )
    assert r.status_code == 200, r.text
    fake_repo.read_many.assert_awaited_once()


def test_fetch_validates_interval(client: TestClient) -> None:
    r = client.post(
        "/v1/data/fetch",
        json={
            "tickers": ["SPY"],
            "start": "2024-01-01",
            "end": "2024-01-31",
            "interval": "BAD",
        },
    )
    assert r.status_code == 422
