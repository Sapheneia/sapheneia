"""TimescaleDB-backed prices repository with read-through caching."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta

import asyncpg

from . import yfinance_client


class PricesRepo:
    """Encapsulates all prices-table reads and writes.

    The repo is created with an ``asyncpg.Pool`` and a fetch concurrency cap.
    Callers do not need to know about the cache miss path — ``read_through``
    is the only entry point for end users.
    """

    def __init__(self, pool: asyncpg.Pool, *, fetch_concurrency: int = 8):
        self._pool = pool
        self._semaphore = asyncio.Semaphore(fetch_concurrency)

    # ----- raw reads ---------------------------------------------------------

    async def read(
        self,
        ticker: str,
        start: date,
        end: date,
        interval: str = "1d",
        end_date: date | None = None,
    ) -> list[asyncpg.Record]:
        """Read existing rows from TimescaleDB without fetching anything new.

        ``end_date`` enforces backtest temporal isolation: rows with
        ``time > end_date`` are never returned, even if present.
        """
        upper = min(end, end_date) if end_date is not None else end
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT time, ticker, open, high, low, close, adj_close, volume
                FROM prices
                WHERE ticker = $1 AND interval = $2
                  AND time >= $3 AND time <= $4
                ORDER BY time
                """,
                ticker,
                interval,
                _to_dt(start),
                _to_dt(upper, end_of_day=True),
            )

    # ----- writes ------------------------------------------------------------

    async def upsert_bars(self, rows: Sequence[dict]) -> int:
        """Insert price bars, ignoring conflicts on ``(ticker, interval, time)``.

        Returns the number of rows inserted (rough — driver doesn't always
        report this precisely; we use the sequence length as an upper bound).
        """
        if not rows:
            return 0
        records = [
            (
                r["time"],
                r["ticker"],
                r.get("open"),
                r.get("high"),
                r.get("low"),
                r.get("close"),
                r.get("adj_close"),
                r.get("volume"),
                r.get("interval", "1d"),
            )
            for r in rows
        ]
        async with self._pool.acquire() as conn:
            # executemany returns None for INSERT in asyncpg; rely on caller
            await conn.executemany(
                """
                INSERT INTO prices
                  (time, ticker, open, high, low, close, adj_close, volume, interval)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (ticker, interval, time) DO NOTHING
                """,
                records,
            )
        return len(records)

    # ----- read-through ------------------------------------------------------

    async def read_through(
        self,
        ticker: str,
        start: date,
        end: date,
        interval: str = "1d",
        end_date: date | None = None,
    ) -> list[asyncpg.Record]:
        """Read rows; on cache miss, fetch from yfinance, write, then re-read.

        Cache miss = the contiguous date span [start, end] is not fully
        covered by existing rows. We do not detect intra-span gaps; if the
        cache has rows but is incomplete, the upper bound is extended to fill
        forward. ``end_date`` is honored on the way back out.
        """
        existing = await self.read(ticker, start, end, interval, end_date=end_date)
        if _covers(existing, start, end):
            return existing

        upper = end
        rows = await yfinance_client.fetch(ticker, start, upper + timedelta(days=1), interval)
        for r in rows:
            r["interval"] = interval
        await self.upsert_bars(rows)
        return await self.read(ticker, start, end, interval, end_date=end_date)

    async def read_many(
        self,
        tickers: Iterable[str],
        start: date,
        end: date,
        interval: str = "1d",
        end_date: date | None = None,
    ) -> dict[str, list[asyncpg.Record]]:
        results: dict[str, list[asyncpg.Record]] = {}
        for t in tickers:
            results[t] = await self.read_through(t, start, end, interval, end_date=end_date)
        return results


# ----- helpers --------------------------------------------------------------


def _to_dt(d: date, end_of_day: bool = False) -> datetime:
    if end_of_day:
        return datetime(d.year, d.month, d.day, 23, 59, 59, 999999)
    return datetime(d.year, d.month, d.day)


def _covers(rows: Sequence[asyncpg.Record], start: date, end: date) -> bool:
    """Cheap heuristic: rows present and span endpoints are within 7 days."""
    if not rows:
        return False
    first = rows[0]["time"].date()
    last = rows[-1]["time"].date()
    if first - start > timedelta(days=7):
        return False
    if end - last > timedelta(days=7):
        return False
    return True
