"""Schema assertions against a real, migrated TimescaleDB.

Uses the root ``timescaledb_psycopg_dsn`` fixture, which prefers an externally
supplied database (``TIMESCALEDB_HOST``) and falls back to testcontainers.

The migration is the only place these invariants are expressed, and a wrong key
here is silent: ``ON CONFLICT`` simply drops rows that should have been stored.
So they are asserted against a database, not a mock.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def conn(timescaledb_psycopg_dsn: str):
    psycopg = pytest.importorskip("psycopg")
    connection = psycopg.connect(
        timescaledb_psycopg_dsn.replace("postgresql+psycopg://", "postgresql://")
    )
    try:
        yield connection
    finally:
        connection.close()


def _pk_columns(conn, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary
            """,
            (table,),
        )
        return sorted(r[0] for r in cur.fetchall())


def test_every_expected_table_exists(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = {r[0] for r in cur.fetchall()}
    assert {
        "tickers",
        "models",
        "runs",
        "prices",
        "forecasts",
        "trades",
        "equity",
        "metrics",
    } <= tables


def test_run_scoped_tables_are_hypertables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT hypertable_name FROM timescaledb_information.hypertables")
        names = {r[0] for r in cur.fetchall()}
    assert {"prices", "forecasts", "trades", "equity"} <= names


def test_forecast_identity_is_six_columns(conn) -> None:
    """Two configs on the same run+ticker+day must both be storable.

    A 3-column (run_id, ticker, time) key collapses them, and the repository's
    ON CONFLICT DO NOTHING then silently discards the second forecast.
    """
    assert _pk_columns(conn, "forecasts") == sorted(
        ["run_id", "ticker", "time", "model_id", "context_size", "horizon_size"]
    )


def test_forecast_cache_lookup_index_exists(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_forecasts_cache_lookup'")
        row = cur.fetchone()
    assert row is not None, "cache lookup index missing"
    definition = row[0]
    for col in ("model_id", "ticker", "time", "context_size", "horizon_size"):
        assert col in definition
    # trading_horizon is deliberately excluded: a forecast does not depend on it.
    assert "trading_horizon" not in definition


def test_runs_has_owner_id_for_reconciler_scoping(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'runs'")
        cols = {r[0] for r in cur.fetchall()}
    assert "owner_id" in cols


def test_runs_filter_columns_are_indexed(conn) -> None:
    """``RunsRepository.list()`` exposes ticker and model_id as filters."""
    with conn.cursor() as cur:
        cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'runs'")
        names = {r[0] for r in cur.fetchall()}
    assert {"ix_runs_ticker", "ix_runs_model"} <= names


def test_accumulated_money_columns_are_numeric(conn) -> None:
    """Float accumulation drift shows up directly in reported Sharpe/CAGR."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE (table_name = 'trades' AND column_name IN ('size', 'price', 'value'))
               OR (table_name = 'equity' AND column_name IN ('cash', 'position', 'equity'))
            """
        )
        rows = cur.fetchall()
    assert rows, "expected trades/equity money columns"
    for table, column, dtype in rows:
        assert dtype == "numeric", f"{table}.{column} is {dtype}, expected numeric"


def test_prices_ticker_references_tickers(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = 'prices'
              AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = 'ticker'
            """
        )
        assert cur.fetchone()[0] == 1


def test_run_scoped_rows_cascade_on_run_delete(conn) -> None:
    """``RunsRepository.delete()`` must not be able to leave orphans."""
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tickers (ticker, asset_class) VALUES ('ZZZ','test')")
        cur.execute(
            "INSERT INTO models (model_id, family, status) VALUES ('m/test','chronos','working')"
        )
        cur.execute(
            """
            INSERT INTO runs (run_id, experiment_id, ticker, model_id, strategy_type, config)
            VALUES ('cascade-run', 'exp', 'ZZZ', 'm/test', 'threshold', '{}'::jsonb)
            """
        )
        cur.execute(
            """
            INSERT INTO forecasts
              (time, run_id, ticker, model_id, context_size, horizon_size, median)
            VALUES (now(), 'cascade-run', 'ZZZ', 'm/test', 10, 5, ARRAY[1.0])
            """
        )
        cur.execute(
            """
            INSERT INTO trades (time, run_id, iteration_idx, ticker, action, size, price, value)
            VALUES (now(), 'cascade-run', 0, 'ZZZ', 'BUY', 1.5, 100.25, 150.375)
            """
        )
        cur.execute("DELETE FROM runs WHERE run_id = 'cascade-run'")
        cur.execute("SELECT COUNT(*) FROM forecasts WHERE run_id = 'cascade-run'")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT COUNT(*) FROM trades WHERE run_id = 'cascade-run'")
        assert cur.fetchone()[0] == 0
    conn.rollback()


def test_two_forecast_configs_coexist_in_one_run(conn) -> None:
    """The regression the 6-column key exists to prevent.

    Same run, ticker and timestamp at two context sizes: both rows must persist.
    Under the old 3-column key the second was silently dropped.
    """
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tickers (ticker, asset_class) VALUES ('YYY','test')")
        cur.execute(
            "INSERT INTO models (model_id, family, status) VALUES ('m/two','chronos','working')"
        )
        cur.execute(
            """
            INSERT INTO runs (run_id, experiment_id, ticker, model_id, strategy_type, config)
            VALUES ('two-cfg', 'exp', 'YYY', 'm/two', 'threshold', '{}'::jsonb)
            """
        )
        for context_size in (32, 64):
            cur.execute(
                """
                INSERT INTO forecasts
                  (time, run_id, ticker, model_id, context_size, horizon_size, median)
                VALUES ('2024-01-02T00:00:00Z', 'two-cfg', 'YYY', 'm/two', %s, 5, ARRAY[1.0])
                ON CONFLICT (run_id, ticker, time, model_id, context_size, horizon_size)
                DO NOTHING
                """,
                (context_size,),
            )
        cur.execute("SELECT COUNT(*) FROM forecasts WHERE run_id = 'two-cfg'")
        assert cur.fetchone()[0] == 2, "second forecast configuration was dropped"
    conn.rollback()
