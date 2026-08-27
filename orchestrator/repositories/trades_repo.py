"""Trades and equity hypertable writes.

``trades`` and ``equity`` store monetary quantities as ``NUMERIC``. asyncpg
binds ``NUMERIC`` from ``decimal.Decimal`` and rejects raw floats, so the
conversion happens here — at the persistence boundary — rather than forcing
every caller to think about it.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

import asyncpg

from shared.timeutils import ensure_utc

#: Matches NUMERIC(20, 8) in the schema.
_QUANTUM = Decimal("0.00000001")


def _money(value: float | Decimal | None) -> Decimal | None:
    """Convert a float to the Decimal asyncpg needs for a NUMERIC column."""
    if value is None:
        return None
    try:
        # str() first: Decimal(float) would carry the float's binary artefacts
        # into the exact representation we just switched to NUMERIC to avoid.
        return Decimal(str(value)).quantize(_QUANTUM)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"cannot store {value!r} as NUMERIC(20, 8)") from exc


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
                ensure_utc(time),
                run_id,
                iteration_idx,
                ticker,
                action,
                _money(size),
                _money(price),
                _money(value),
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
                ensure_utc(time),
                run_id,
                _money(cash),
                _money(position),
                _money(equity),
            )

    async def list(self, run_id: str) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT time, cash, position, equity FROM equity WHERE run_id = $1 ORDER BY time",
                run_id,
            )
            # Hand back floats: callers do arithmetic and JSON-encode these.
            return [
                {
                    "time": r["time"],
                    "cash": float(r["cash"]) if r["cash"] is not None else None,
                    "position": float(r["position"]) if r["position"] is not None else None,
                    "equity": float(r["equity"]) if r["equity"] is not None else None,
                }
                for r in rows
            ]
