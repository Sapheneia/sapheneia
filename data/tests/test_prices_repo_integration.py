"""Integration tests for the PricesRepo against a real TimescaleDB.

Uses the root ``timescaledb_asyncpg_dsn`` fixture, which prefers an externally
supplied database (``TIMESCALEDB_HOST``) and falls back to testcontainers.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
async def repo(timescaledb_asyncpg_dsn: str, monkeypatch):
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

    pool = await asyncpg.create_pool(timescaledb_asyncpg_dsn, min_size=1, max_size=2)
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
