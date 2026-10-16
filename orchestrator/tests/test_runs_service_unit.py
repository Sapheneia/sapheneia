"""Tests for RunsService.

The endpoint tests swap in an ``AsyncMock`` for the whole service, so the real
class — the semaphore, the batch error path, cancel-in-flight, and the
registry check — was never instantiated by any test.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from orchestrator.services.runs_service import RunsService, make_run_id
from shared.model_registry import UnknownModelError

TINY = "amazon/chronos-t5-tiny"


def _service(**kw) -> tuple[RunsService, AsyncMock, AsyncMock]:
    runs_repo = AsyncMock()
    inner = AsyncMock()
    svc = RunsService(
        runs_repo=runs_repo,
        inner_loop=inner,
        max_concurrent_runs=kw.pop("max_concurrent_runs", 4),
        heartbeat_refresh_interval=kw.pop("heartbeat_refresh_interval", 3600.0),
        owner_id=kw.pop("owner_id", "worker-a"),
    )
    return svc, runs_repo, inner


def test_make_run_id_is_filesystem_safe() -> None:
    rid = make_run_id("exp1", "SPY", TINY, suffix="abc123")
    assert "/" not in rid
    assert rid.startswith("exp1__SPY__amazon_chronos-t5-tiny__")
    assert rid.endswith("_abc123")


async def test_submit_registers_ticker_model_and_stamps_owner(sample_strategy) -> None:
    svc, runs_repo, inner = _service()

    run_id, status = await svc.submit(sample_strategy)
    await asyncio.gather(*svc._active_tasks.values(), return_exceptions=True)

    assert status == "pending"
    runs_repo.ensure_ticker.assert_awaited_once_with(sample_strategy["evaluation"]["ticker"])
    runs_repo.ensure_model.assert_awaited_once_with(TINY, "chronos", "working")

    _args, kwargs = runs_repo.create.await_args
    assert kwargs["run_id"] == run_id
    assert kwargs["model_id"] == TINY
    # Stamped so the reconciler can tell this instance's runs from another's.
    assert kwargs["owner_id"] == "worker-a"
    inner.run.assert_awaited_once()


async def test_submit_rejects_a_model_missing_from_the_registry(sample_strategy) -> None:
    """An unroutable model must fail at submit, not silently hit the wrong container."""
    sample_strategy["forecast"]["model"] = "acme/not-a-model"
    svc, runs_repo, _ = _service()

    with pytest.raises(UnknownModelError):
        await svc.submit(sample_strategy)
    runs_repo.create.assert_not_awaited()


async def test_submit_batch_isolates_a_bad_strategy(sample_strategy) -> None:
    svc, _runs_repo, _inner = _service()
    bad = {"metadata": {}}  # fails StrategyConfig validation

    results = await svc.submit_batch([sample_strategy, bad, sample_strategy])
    await asyncio.gather(*svc._active_tasks.values(), return_exceptions=True)

    assert len(results) == 3
    # The rejected item carries its own index, a null run_id and an error code —
    # it is not a sentinel run_id the caller would then poll as "not_found".
    assert results[1].index == 1
    assert results[1].status == "rejected"
    assert results[1].run_id is None
    assert results[1].error_code
    # The valid neighbours still submitted.
    assert results[0].status == "pending" and results[0].run_id
    assert results[2].status == "pending" and results[2].run_id


async def test_semaphore_caps_concurrent_runs(sample_strategy) -> None:
    svc, _runs_repo, inner = _service(max_concurrent_runs=2)
    in_flight = 0
    peak = 0
    release = asyncio.Event()

    async def slow_run(*_a, **_kw):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await release.wait()
        in_flight -= 1

    inner.run.side_effect = slow_run

    for _ in range(5):
        await svc.submit(sample_strategy)
    await asyncio.sleep(0.05)
    assert peak == 2, f"semaphore let {peak} runs through with a cap of 2"

    release.set()
    await asyncio.gather(*svc._active_tasks.values(), return_exceptions=True)


async def test_cancel_stops_an_in_flight_run(sample_strategy) -> None:
    svc, runs_repo, inner = _service()
    started = asyncio.Event()

    async def blocking_run(*_a, **_kw):
        started.set()
        await asyncio.Event().wait()  # never completes

    inner.run.side_effect = blocking_run

    run_id, _ = await svc.submit(sample_strategy)
    await started.wait()

    assert await svc.cancel(run_id) is True
    runs_repo.update_status.assert_any_await(
        run_id, "cancelled", error="cancelled by request", completed=True
    )


async def test_cancel_returns_false_for_an_unknown_run() -> None:
    svc, _runs_repo, _inner = _service()
    assert await svc.cancel("no-such-run") is False


async def test_queued_run_heartbeats_while_waiting_for_a_slot(sample_strategy) -> None:
    """A run waiting on the semaphore must keep its heartbeat fresh.

    Otherwise the reconciler mistakes a queued run for an orphan and fails it.
    """
    svc, runs_repo, inner = _service(max_concurrent_runs=1, heartbeat_refresh_interval=0.01)
    release = asyncio.Event()

    async def slow_run(*_a, **_kw):
        await release.wait()

    inner.run.side_effect = slow_run

    await svc.submit(sample_strategy)  # takes the only slot
    await svc.submit(sample_strategy)  # queues, should heartbeat
    await asyncio.sleep(0.06)

    assert runs_repo.heartbeat.await_count >= 1

    release.set()
    await asyncio.gather(*svc._active_tasks.values(), return_exceptions=True)
