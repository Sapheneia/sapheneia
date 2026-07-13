"""Trades and equity hypertable writes."""

from __future__ import annotations

from datetime import datetime

import asyncpg


class TradesRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def write(
        self,
        *,
        run_id: str,
        iteration_idx: int,
        time: datetime,
        ticker: str,
        action: str,
        size: float,
        price: float,
        value: float,
        reason: str | None = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO trades
                  (time, run_id, iteration_idx, ticker, action, size, price, value, reason)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (run_id, iteration_idx, time) DO NOTHING
                """,
                time,
                run_id,
                iteration_idx,
                ticker,
                action,
                size,
                price,
                value,
                reason,
            )


class EquityRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def write(
        self,
        *,
        run_id: str,
        time: datetime,
        cash: float,
        position: float,
        equity: float,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO equity (time, run_id, cash, position, equity)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (run_id, time) DO UPDATE SET
                    cash = EXCLUDED.cash,
                    position = EXCLUDED.position,
                    equity = EXCLUDED.equity
                """,
                time,
                run_id,
                cash,
                position,
                equity,
            )

    async def list(self, run_id: str) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT time, cash, position, equity FROM equity WHERE run_id = $1 ORDER BY time",
                run_id,
            )
            return [dict(r) for r in rows]
