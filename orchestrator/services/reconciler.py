"""Periodic reconciler: marks stuck runs as failed."""

from __future__ import annotations

import asyncio
import logging

from ..repositories.runs_repo import RunsRepository

logger = logging.getLogger("sapheneia.orchestrator.reconciler")


async def heartbeat_reconciler_loop(
    repo: RunsRepository,
    interval: float,
    stale_after: float,
    *,
    owner_id: str | None = None,
) -> None:
    """Periodically fail runs whose heartbeat has gone stale.

    Args:
        repo: Runs repository.
        interval: Seconds between sweeps.
        stale_after: A run is stale once its heartbeat is older than this. It
            must exceed the longest single blocking call in the inner loop (the
            forecast timeout), or live runs get failed mid-flight.
        owner_id: Restrict reconciliation to runs claimed by this instance.
            ``None`` reconciles every owner's orphans, which is correct only for
            a single-instance deployment.
    """
    while True:
        try:
            n = await repo.reconcile_stale(stale_after, owner_id=owner_id)
            if n:
                logger.warning("Reconciler marked %d stale runs as failed", n)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Reconciler iteration failed")
        await asyncio.sleep(interval)
