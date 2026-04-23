"""Periodic reconciler: marks stuck runs as failed."""

from __future__ import annotations

import asyncio
import logging

from ..repositories.runs_repo import RunsRepository

logger = logging.getLogger("sapheneia.orchestrator.reconciler")


async def heartbeat_reconciler_loop(
    repo: RunsRepository, interval: float, stale_after: float
) -> None:
    while True:
        try:
            n = await repo.reconcile_stale(stale_after)
            if n:
                logger.warning("Reconciler marked %d stale runs as failed", n)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Reconciler iteration failed")
        await asyncio.sleep(interval)
