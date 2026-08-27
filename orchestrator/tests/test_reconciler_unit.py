"""Tests for the heartbeat reconciler loop.

This is the stale-run recovery mechanism the architecture calls out by name,
and it previously had no test at any level.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from unittest.mock import AsyncMock

import pytest

from orchestrator.services.reconciler import heartbeat_reconciler_loop


async def _run_briefly(coro_fn, *, ticks: float = 0.05) -> None:
    task = asyncio.create_task(coro_fn)
    await asyncio.sleep(ticks)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def test_reconciler_passes_stale_threshold_and_owner() -> None:
    repo = AsyncMock()
    repo.reconcile_stale.return_value = 0

    await _run_briefly(
        heartbeat_reconciler_loop(repo, interval=0.01, stale_after=900.0, owner_id="worker-a")
    )

    assert repo.reconcile_stale.await_count >= 1
    _args, kwargs = repo.reconcile_stale.await_args
    assert _args[0] == 900.0
    assert kwargs["owner_id"] == "worker-a"


async def test_reconciler_warns_when_it_reaps_runs(caplog) -> None:
    repo = AsyncMock()
    repo.reconcile_stale.return_value = 3

    with caplog.at_level(logging.WARNING):
        await _run_briefly(heartbeat_reconciler_loop(repo, interval=0.01, stale_after=1.0))

    assert any("marked 3 stale runs" in r.getMessage() for r in caplog.records)


async def test_reconciler_survives_a_failing_iteration() -> None:
    """A transient DB error must not kill the loop — it runs for the process life."""
    repo = AsyncMock()
    repo.reconcile_stale.side_effect = [RuntimeError("connection reset"), 0, 0, 0, 0, 0, 0, 0]

    await _run_briefly(heartbeat_reconciler_loop(repo, interval=0.01, stale_after=1.0))

    # Kept going after the exception rather than exiting on the first failure.
    assert repo.reconcile_stale.await_count >= 2


async def test_reconciler_propagates_cancellation() -> None:
    repo = AsyncMock()
    repo.reconcile_stale.return_value = 0
    task = asyncio.create_task(heartbeat_reconciler_loop(repo, interval=0.01, stale_after=1.0))
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
