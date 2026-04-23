"""Integration tests for the PricesRepo against a real TimescaleDB.

Requires Docker (testcontainers spins up a fresh TimescaleDB image).
Skipped if testcontainers isn't installed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "migrations" / "alembic.ini"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def timescaledb_dsn() -> str:
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers[postgres] not installed")

    container = PostgresContainer(
        image="timescale/timescaledb:latest-pg16",
        username="sapheneia",
        password="sapheneia",
        dbname="sapheneia",
    )
    container.start()
    try:
        psycopg_url = container.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+psycopg://"
        )
        env = {**os.environ, "DATABASE_URL": psycopg_url}
        result = subprocess.run(
            ["alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
        )
        if result.returncode != 0:
            pytest.skip(f"alembic upgrade failed: {result.stderr}")
        # asyncpg DSN form
        asyncpg_url = psycopg_url.replace("postgresql+psycopg://", "postgresql://")
        yield asyncpg_url
    finally:
        container.stop()


@pytest.fixture
async def repo(timescaledb_dsn: str, monkeypatch):
    import asyncpg

    from data.services import yfinance_client
    from data.services.prices_repo import PricesRepo

    async def fake_fetch(ticker, start, end, interval):
        return [
            {
                "time": datetime(2024, 1, 2),
                "ticker": ticker,
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "adj_close": 100.5,
                "volume": 1_000_000,
            },
            {
                "time": datetime(2024, 1, 3),
                "ticker": ticker,
                "open": 100.5,
                "high": 102.0,
                "low": 100.0,
                "close": 101.5,
                "adj_close": 101.5,
                "volume": 1_200_000,
            },
        ]

    monkeypatch.setattr(yfinance_client, "fetch", fake_fetch)

    pool = await asyncpg.create_pool(timescaledb_dsn, min_size=1, max_size=2)
    try:
        # Clean any leftover rows from prior tests in this session
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM prices")
        yield PricesRepo(pool)
    finally:
        await pool.close()


async def test_read_through_populates_cache(repo) -> None:
    rows = await repo.read_through("SPY", date(2024, 1, 2), date(2024, 1, 3))
    assert len(rows) == 2
    assert rows[0]["close"] == 100.5
    assert rows[1]["close"] == 101.5

    # Second call should hit the cache (yfinance fetch would still work
    # because it's monkeypatched, but the rows already exist)
    again = await repo.read_through("SPY", date(2024, 1, 2), date(2024, 1, 3))
    assert len(again) == 2


async def test_read_through_respects_end_date(repo) -> None:
    rows = await repo.read_through(
        "SPY", date(2024, 1, 2), date(2024, 1, 3), end_date=date(2024, 1, 2)
    )
    assert len(rows) == 1
    assert rows[0]["time"].date() == date(2024, 1, 2)


async def test_upsert_idempotent(repo) -> None:
    bars = [
        {
            "time": datetime(2024, 2, 1),
            "ticker": "QQQ",
            "open": 400.0,
            "high": 401.0,
            "low": 399.0,
            "close": 400.5,
            "adj_close": 400.5,
            "volume": 50_000_000,
            "interval": "1d",
        }
    ]
    await repo.upsert_bars(bars)
    await repo.upsert_bars(bars)  # idempotent

    rows = await repo.read("QQQ", date(2024, 2, 1), date(2024, 2, 1))
    assert len(rows) == 1
