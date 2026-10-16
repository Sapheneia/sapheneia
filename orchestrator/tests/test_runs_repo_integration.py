"""Integration tests for the orchestrator repositories against a real database.

Every other orchestrator test mocks the repository layer, so the SQL itself —
`reconcile_stale`'s owner-scoping predicate and interval arithmetic,
`update_status`'s COALESCE/clear_error branch, the forecast cache's 6-column
ON CONFLICT and its scope-aware JOIN — had never executed against Postgres. A
wrong column name or a broken predicate cannot be caught by an AsyncMock.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from orchestrator.repositories.forecasts_repo import ForecastsRepository
from orchestrator.repositories.runs_repo import RunsRepository
from orchestrator.repositories.trades_repo import EquityRepository, TradesRepository

pytestmark = pytest.mark.integration

TICKER = "SPY"
MODEL = "amazon/chronos-t5-tiny"


@pytest.fixture
async def pool(timescaledb_asyncpg_dsn: str):
    import asyncpg

    p = await asyncpg.create_pool(timescaledb_asyncpg_dsn, min_size=1, max_size=3)
    try:
        async with p.acquire() as conn:
            await conn.execute("DELETE FROM runs")
        yield p
    finally:
        await p.close()


@pytest.fixture
async def repos(pool):
    runs = RunsRepository(pool)
    await runs.ensure_ticker(TICKER)
    await runs.ensure_model(MODEL, "chronos")
    return {
        "runs": runs,
        "forecasts": ForecastsRepository(pool),
        "trades": TradesRepository(pool),
        "equity": EquityRepository(pool),
        "pool": pool,
    }


async def _create(runs: RunsRepository, run_id: str, *, owner_id=None, experiment="exp") -> None:
    await runs.create(
        run_id=run_id,
        experiment_id=experiment,
        ticker=TICKER,
        model_id=MODEL,
        strategy_type="threshold",
        config={"k": "v"},
        cache_enabled=True,
        cache_scope="experiment",
        owner_id=owner_id,
    )


async def _age_heartbeat(pool, run_id: str, seconds: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE runs SET heartbeat_at = now() - ($2 || ' seconds')::interval WHERE run_id = $1",
            run_id,
            str(seconds),
        )


# --- reconcile_stale -------------------------------------------------------


async def test_reconcile_stale_fails_only_runs_past_the_threshold(repos, pool) -> None:
    runs = repos["runs"]
    await _create(runs, "fresh")
    await _create(runs, "stale")
    await runs.update_status("fresh", "running")
    await runs.update_status("stale", "running")
    await _age_heartbeat(pool, "stale", 3600)

    assert await runs.reconcile_stale(900) == 1
    assert (await runs.get("fresh"))["status"] == "running"
    stale = await runs.get("stale")
    assert stale["status"] == "failed"
    assert stale["error"] == "heartbeat timeout"
    assert stale["completed_at"] is not None


async def test_reconcile_stale_scopes_to_the_owner(repos, pool) -> None:
    """The headline multi-instance fix: never fail another instance's live run."""
    runs = repos["runs"]
    await _create(runs, "mine", owner_id="worker-a")
    await _create(runs, "theirs", owner_id="worker-b")
    for rid in ("mine", "theirs"):
        await runs.update_status(rid, "running")
        await _age_heartbeat(pool, rid, 3600)

    assert await runs.reconcile_stale(900, owner_id="worker-a") == 1
    assert (await runs.get("mine"))["status"] == "failed"
    assert (await runs.get("theirs"))["status"] == "running"


async def test_owner_scoped_reconcile_still_reclaims_unowned_orphans(repos, pool) -> None:
    runs = repos["runs"]
    await _create(runs, "orphan", owner_id=None)
    await runs.update_status("orphan", "running")
    await _age_heartbeat(pool, "orphan", 3600)

    assert await runs.reconcile_stale(900, owner_id="worker-a") == 1
    assert (await runs.get("orphan"))["status"] == "failed"


async def test_reconcile_stale_covers_pending_runs(repos, pool) -> None:
    """A run never picked up after a restart is an orphan too."""
    runs = repos["runs"]
    await _create(runs, "never-started")
    await _age_heartbeat(pool, "never-started", 3600)

    assert await runs.reconcile_stale(900) == 1
    assert (await runs.get("never-started"))["status"] == "failed"


async def test_reconcile_stale_ignores_terminal_runs(repos, pool) -> None:
    runs = repos["runs"]
    await _create(runs, "done")
    await runs.update_status("done", "completed", completed=True)
    await _age_heartbeat(pool, "done", 3600)

    assert await runs.reconcile_stale(900) == 0
    assert (await runs.get("done"))["status"] == "completed"


# --- update_status ---------------------------------------------------------


async def test_error_is_sticky_without_clear_error(repos) -> None:
    runs = repos["runs"]
    await _create(runs, "r1")
    await runs.update_status("r1", "failed", error="boom")
    await runs.update_status("r1", "running")
    assert (await runs.get("r1"))["error"] == "boom"


async def test_clear_error_removes_a_stale_reconciler_message(repos, pool) -> None:
    """A run the reconciler flagged, that then finished, must not stay dirty."""
    runs = repos["runs"]
    await _create(runs, "r2")
    await runs.update_status("r2", "running")
    await _age_heartbeat(pool, "r2", 3600)
    await runs.reconcile_stale(900)
    assert (await runs.get("r2"))["error"] == "heartbeat timeout"

    await runs.update_status("r2", "completed", completed=True, clear_error=True)
    row = await runs.get("r2")
    assert row["status"] == "completed"
    assert row["error"] is None


async def test_create_is_idempotent(repos) -> None:
    runs = repos["runs"]
    await _create(runs, "dup")
    await _create(runs, "dup", experiment="different")
    row = await runs.get("dup")
    assert row["experiment_id"] == "exp"  # ON CONFLICT DO NOTHING kept the first


# --- forecast cache --------------------------------------------------------


async def test_two_configs_in_one_run_both_persist(repos) -> None:
    """The 6-column identity, exercised through the repository not raw SQL."""
    runs, forecasts = repos["runs"], repos["forecasts"]
    await _create(runs, "cfg")
    when = datetime(2024, 1, 2, tzinfo=UTC)
    for context_size in (32, 64):
        await forecasts.write(
            run_id="cfg",
            ticker=TICKER,
            time=when,
            model_id=MODEL,
            context_size=context_size,
            horizon_size=5,
            median=[1.0, 2.0],
        )
    for context_size in (32, 64):
        hit = await forecasts.lookup(
            model_id=MODEL,
            ticker=TICKER,
            time=when,
            context_size=context_size,
            horizon_size=5,
        )
        assert hit is not None, f"context_size={context_size} was dropped"


async def test_cache_lookup_is_scoped_by_experiment(repos) -> None:
    runs, forecasts = repos["runs"], repos["forecasts"]
    await _create(runs, "in-exp", experiment="exp-a")
    when = datetime(2024, 2, 1, tzinfo=UTC)
    await forecasts.write(
        run_id="in-exp",
        ticker=TICKER,
        time=when,
        model_id=MODEL,
        context_size=10,
        horizon_size=3,
        median=[5.0],
        q10=[4.0],
        q90=[6.0],
    )
    args = dict(model_id=MODEL, ticker=TICKER, time=when, context_size=10, horizon_size=3)

    assert await forecasts.lookup(**args, experiment_id="exp-a") is not None
    assert await forecasts.lookup(**args, experiment_id="exp-other") is None
    globally = await forecasts.lookup(**args)  # unscoped
    assert globally is not None
    assert list(globally["q10"]) == [4.0]


async def test_naive_and_aware_times_resolve_to_the_same_row(repos) -> None:
    """The UTC normalisation must make a naive lookup find an aware write."""
    runs, forecasts = repos["runs"], repos["forecasts"]
    await _create(runs, "tz")
    await forecasts.write(
        run_id="tz",
        ticker=TICKER,
        time=datetime(2024, 3, 4, tzinfo=UTC),
        model_id=MODEL,
        context_size=8,
        horizon_size=2,
        median=[1.0],
    )
    hit = await forecasts.lookup(
        model_id=MODEL,
        ticker=TICKER,
        time=datetime(2024, 3, 4),  # naive
        context_size=8,
        horizon_size=2,
    )
    assert hit is not None


# --- NUMERIC round-trip ----------------------------------------------------


async def test_money_round_trips_without_float_drift(repos) -> None:
    runs, trades, equity = repos["runs"], repos["trades"], repos["equity"]
    await _create(runs, "money")
    when = datetime(2024, 4, 1, tzinfo=UTC)
    await trades.write(
        run_id="money",
        iteration_idx=0,
        time=when,
        ticker=TICKER,
        action="BUY",
        size=0.1 + 0.2,  # 0.30000000000000004 as a float
        price=123.456789,
        value=1234.5678,
    )
    await equity.write(
        run_id="money", time=when, cash=0.1 + 0.2, position=1.5, equity=99999.99999999
    )

    rows = await equity.list("money")
    assert len(rows) == 1
    # Comes back as float for JSON/arithmetic consumers, not Decimal.
    assert isinstance(rows[0]["cash"], float)
    assert rows[0]["cash"] == pytest.approx(0.3)
    assert rows[0]["equity"] == pytest.approx(99999.99999999)

    async with repos["pool"].acquire() as conn:
        stored = await conn.fetchval("SELECT price FROM trades WHERE run_id = 'money'")
    assert str(stored) == "123.45678900"


async def test_cascade_delete_removes_run_scoped_rows(repos) -> None:
    runs, forecasts, trades = repos["runs"], repos["forecasts"], repos["trades"]
    await _create(runs, "casc")
    when = datetime(2024, 5, 1, tzinfo=UTC)
    await forecasts.write(
        run_id="casc",
        ticker=TICKER,
        time=when,
        model_id=MODEL,
        context_size=4,
        horizon_size=1,
        median=[1.0],
    )
    await trades.write(
        run_id="casc",
        iteration_idx=0,
        time=when,
        ticker=TICKER,
        action="HOLD",
        size=0.0,
        price=1.0,
        value=0.0,
    )

    assert await runs.delete("casc") == 1
    async with repos["pool"].acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM forecasts WHERE run_id='casc'") == 0
        assert await conn.fetchval("SELECT count(*) FROM trades WHERE run_id='casc'") == 0
