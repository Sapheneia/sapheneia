"""Forecast cache repository (read/write/delete)."""

from __future__ import annotations

from datetime import datetime

import asyncpg


class ForecastsRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def lookup(
        self,
        *,
        model_id: str,
        ticker: str,
        time: datetime,
        context_size: int,
        horizon_size: int,
        experiment_id: str | None = None,
    ) -> dict | None:
        """Find a usable cache row. Scope-aware via experiment_id JOIN."""
        if experiment_id is not None:
            sql = """
                SELECT f.median, f.q10, f.q90
                FROM forecasts f JOIN runs r ON f.run_id = r.run_id
                WHERE f.model_id = $1 AND f.ticker = $2 AND f.time = $3
                  AND f.context_size = $4 AND f.horizon_size = $5
                  AND r.experiment_id = $6
                LIMIT 1
            """
            params = (model_id, ticker, time, context_size, horizon_size, experiment_id)
        else:
            sql = """
                SELECT median, q10, q90
                FROM forecasts
                WHERE model_id = $1 AND ticker = $2 AND time = $3
                  AND context_size = $4 AND horizon_size = $5
                LIMIT 1
            """
            params = (model_id, ticker, time, context_size, horizon_size)

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params)
            return dict(row) if row else None

    async def write(
        self,
        *,
        run_id: str,
        ticker: str,
        time: datetime,
        model_id: str,
        context_size: int,
        horizon_size: int,
        median: list[float],
        q10: list[float] | None = None,
        q90: list[float] | None = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO forecasts
                  (time, run_id, ticker, model_id, context_size, horizon_size, median, q10, q90)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (run_id, ticker, time) DO NOTHING
                """,
                time,
                run_id,
                ticker,
                model_id,
                context_size,
                horizon_size,
                median,
                q10,
                q90,
            )

    async def delete_by_experiment(self, experiment_id: str) -> int:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM forecasts
                WHERE run_id IN (SELECT run_id FROM runs WHERE experiment_id = $1)
                """,
                experiment_id,
            )
            return int(result.split()[-1]) if result else 0

    async def delete_older_than(self, seconds: int) -> int:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM forecasts WHERE created_at < now() - INTERVAL '{int(seconds)} seconds'"
            )
            return int(result.split()[-1]) if result else 0
