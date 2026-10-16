"""asyncpg repository for the runs / metrics tables."""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from shared.tickers import ENSURE_TICKER_SQL, UNKNOWN_ASSET_CLASS


class RunsRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def ensure_ticker(self, ticker: str, asset_class: str = UNKNOWN_ASSET_CLASS) -> None:
        """Pre-register a ticker so `runs.ticker`'s FK is satisfiable.

        `data` owns the `tickers` table; this is a narrow pre-registration for
        the run row and shares its SQL so the two sites cannot drift.
        """
        async with self._pool.acquire() as conn:
            await conn.execute(ENSURE_TICKER_SQL, ticker, asset_class)

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
        owner_id: str | None = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO runs
                  (run_id, experiment_id, ticker, model_id, strategy_type,
                   config, cache_enabled, cache_scope, status, owner_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending', $9)
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
                owner_id,
            )

    async def update_status(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
        completed: bool = False,
        clear_error: bool = False,
    ) -> None:
        """Update a run's status.

        ``clear_error`` exists because ``error`` is otherwise sticky: the
        ``COALESCE`` below preserves any prior message so a later status update
        cannot erase it. Without a way to clear it, a run that the reconciler
        transiently flagged and that then finished successfully would remain
        ``completed`` *with* a stale ``heartbeat timeout`` error forever.
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE runs
                SET status = $2,
                    error = CASE WHEN $5 THEN NULL ELSE COALESCE($3, error) END,
                    completed_at = CASE WHEN $4 THEN now() ELSE completed_at END,
                    heartbeat_at = now()
                WHERE run_id = $1
                """,
                run_id,
                status,
                error,
                completed,
                clear_error,
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

    async def reconcile_stale(
        self, stale_after_seconds: float, *, owner_id: str | None = None
    ) -> int:
        """Mark stuck runs as failed.

        Covers both ``running`` runs whose heartbeat is stale, and ``pending``
        runs that were never picked up (e.g. the orchestrator restarted and the
        in-memory task that would have flipped them to ``running`` is gone).

        ``owner_id`` scopes reconciliation to runs this process claimed. Runs are
        claimed by the instance that created them (``runs.owner_id``); without
        that predicate a second orchestrator instance would happily fail the
        first instance's live runs. Passing ``None`` reconciles orphans of *any*
        owner and is only correct for a single-instance deployment — see
        ``ORCHESTRATOR_RECONCILE_ALL_OWNERS``.
        """
        stale = int(stale_after_seconds)
        params: list[Any] = []
        owner_clause = ""
        if owner_id is not None:
            params.append(owner_id)
            owner_clause = f"AND (owner_id IS NULL OR owner_id = ${len(params)})"
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"""
                UPDATE runs
                SET status = 'failed',
                    error = COALESCE(error, 'heartbeat timeout'),
                    completed_at = now()
                WHERE status IN ('running', 'pending')
                  AND heartbeat_at < now() - INTERVAL '{stale} seconds'
                  {owner_clause}
                """,
                *params,
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
