"""asyncpg repository for the runs / metrics tables."""

from __future__ import annotations

import json
from typing import Any

import asyncpg


class RunsRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def ensure_ticker(self, ticker: str, asset_class: str = "unknown") -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO tickers (ticker, asset_class) VALUES ($1, $2) ON CONFLICT (ticker) DO NOTHING",
                ticker,
                asset_class,
            )

    async def ensure_model(self, model_id: str, family: str, status: str = "working") -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO models (model_id, family, status)
                VALUES ($1, $2, $3)
                ON CONFLICT (model_id) DO NOTHING
                """,
                model_id,
                family,
                status,
            )

    async def create(
        self,
        *,
        run_id: str,
        experiment_id: str,
        ticker: str,
        model_id: str,
        strategy_type: str,
        config: dict[str, Any],
        cache_enabled: bool,
        cache_scope: str,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO runs
                  (run_id, experiment_id, ticker, model_id, strategy_type,
                   config, cache_enabled, cache_scope, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
                ON CONFLICT (run_id) DO NOTHING
                """,
                run_id,
                experiment_id,
                ticker,
                model_id,
                strategy_type,
                json.dumps(config),
                cache_enabled,
                cache_scope,
            )

    async def update_status(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
        completed: bool = False,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE runs
                SET status = $2,
                    error = COALESCE($3, error),
                    completed_at = CASE WHEN $4 THEN now() ELSE completed_at END,
                    heartbeat_at = now()
                WHERE run_id = $1
                """,
                run_id,
                status,
                error,
                completed,
            )

    async def heartbeat(self, run_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE runs SET heartbeat_at = now() WHERE run_id = $1", run_id)

    async def get(self, run_id: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT r.*, m.sharpe, m.sortino, m.cagr, m.calmar,
                       m.max_drawdown, m.win_rate, m.total_return, m.extra
                FROM runs r LEFT JOIN metrics m ON r.run_id = m.run_id
                WHERE r.run_id = $1
                """,
                run_id,
            )
            return dict(row) if row else None

    async def list(
        self,
        *,
        experiment_id: str | None = None,
        status: str | None = None,
        ticker: str | None = None,
        model_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        for col, val in (
            ("experiment_id", experiment_id),
            ("status", status),
            ("ticker", ticker),
            ("model_id", model_id),
        ):
            if val is not None:
                params.append(val)
                clauses.append(f"{col} = ${len(params)}")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT run_id, experiment_id, ticker, model_id, strategy_type,
                       status, started_at, completed_at, error
                FROM runs
                {where}
                ORDER BY started_at DESC
                LIMIT ${len(params)}
                """,
                *params,
            )
            return [dict(r) for r in rows]

    async def reconcile_stale(self, stale_after_seconds: float) -> int:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"""
                UPDATE runs
                SET status = 'failed',
                    error = COALESCE(error, 'heartbeat timeout'),
                    completed_at = now()
                WHERE status = 'running'
                  AND heartbeat_at < now() - INTERVAL '{int(stale_after_seconds)} seconds'
                """
            )
            # asyncpg returns "UPDATE n"
            return int(result.split()[-1]) if result else 0

    async def delete(self, run_id: str) -> int:
        async with self._pool.acquire() as conn:
            result = await conn.execute("DELETE FROM runs WHERE run_id = $1", run_id)
            return int(result.split()[-1]) if result else 0


class MetricsRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def write(self, run_id: str, metrics: dict[str, Any]) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO metrics (run_id, sharpe, sortino, cagr, calmar,
                                     max_drawdown, win_rate, total_return, extra)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (run_id) DO UPDATE SET
                    sharpe       = EXCLUDED.sharpe,
                    sortino      = EXCLUDED.sortino,
                    cagr         = EXCLUDED.cagr,
                    calmar       = EXCLUDED.calmar,
                    max_drawdown = EXCLUDED.max_drawdown,
                    win_rate     = EXCLUDED.win_rate,
                    total_return = EXCLUDED.total_return,
                    extra        = EXCLUDED.extra
                """,
                run_id,
                metrics.get("sharpe"),
                metrics.get("sortino"),
                metrics.get("cagr"),
                metrics.get("calmar"),
                metrics.get("max_drawdown"),
                metrics.get("win_rate"),
                metrics.get("total_return"),
                (json.dumps(metrics.get("extra")) if metrics.get("extra") is not None else None),
            )
