"""initial schema: tickers, models, runs, prices, forecasts, trades, equity, metrics

Revision ID: 001_initial
Revises:
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # Reference / metadata ------------------------------------------------
    op.execute(
        """
        CREATE TABLE tickers (
            ticker      TEXT PRIMARY KEY,
            asset_class TEXT NOT NULL,
            description TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE models (
            model_id TEXT PRIMARY KEY,
            family   TEXT NOT NULL,
            status   TEXT NOT NULL,
            notes    TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE runs (
            run_id         TEXT PRIMARY KEY,
            experiment_id  TEXT NOT NULL,
            ticker         TEXT NOT NULL REFERENCES tickers(ticker),
            model_id       TEXT NOT NULL REFERENCES models(model_id),
            strategy_type  TEXT NOT NULL,
            config         JSONB NOT NULL,
            cache_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
            cache_scope    TEXT NOT NULL DEFAULT 'experiment',
            started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            heartbeat_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at   TIMESTAMPTZ,
            status         TEXT NOT NULL DEFAULT 'pending',
            error          TEXT
        )
        """
    )
    op.create_index("ix_runs_experiment", "runs", ["experiment_id", "started_at"])
    op.create_index("ix_runs_status", "runs", ["status", "heartbeat_at"])

    # Hypertables ---------------------------------------------------------
    op.execute(
        """
        CREATE TABLE prices (
            time      TIMESTAMPTZ NOT NULL,
            ticker    TEXT NOT NULL,
            open      DOUBLE PRECISION,
            high      DOUBLE PRECISION,
            low       DOUBLE PRECISION,
            close     DOUBLE PRECISION,
            adj_close DOUBLE PRECISION,
            volume    BIGINT,
            interval  TEXT NOT NULL DEFAULT '1d',
            PRIMARY KEY (ticker, interval, time)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('prices', 'time', chunk_time_interval => INTERVAL '90 days')"
    )

    op.execute(
        """
        CREATE TABLE forecasts (
            time          TIMESTAMPTZ NOT NULL,
            run_id        TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
            ticker        TEXT NOT NULL,
            model_id      TEXT NOT NULL,
            context_size  INTEGER NOT NULL,
            horizon_size  INTEGER NOT NULL,
            median        DOUBLE PRECISION[] NOT NULL,
            q10           DOUBLE PRECISION[],
            q90           DOUBLE PRECISION[],
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (run_id, ticker, time)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('forecasts', 'time', chunk_time_interval => INTERVAL '30 days')"
    )
    op.create_index(
        "ix_forecasts_cache_lookup",
        "forecasts",
        ["model_id", "ticker", "time", "context_size", "horizon_size"],
    )

    op.execute(
        """
        CREATE TABLE trades (
            time          TIMESTAMPTZ NOT NULL,
            run_id        TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
            iteration_idx INTEGER NOT NULL,
            ticker        TEXT NOT NULL,
            action        TEXT NOT NULL,
            size          DOUBLE PRECISION,
            price         DOUBLE PRECISION,
            value         DOUBLE PRECISION,
            reason        TEXT,
            -- TimescaleDB requires the partition column ('time') in any unique index/PK
            PRIMARY KEY (run_id, iteration_idx, time)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('trades', 'time', chunk_time_interval => INTERVAL '30 days')"
    )

    op.execute(
        """
        CREATE TABLE equity (
            time     TIMESTAMPTZ NOT NULL,
            run_id   TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
            cash     DOUBLE PRECISION,
            position DOUBLE PRECISION,
            equity   DOUBLE PRECISION,
            PRIMARY KEY (run_id, time)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('equity', 'time', chunk_time_interval => INTERVAL '30 days')"
    )

    op.execute(
        """
        CREATE TABLE metrics (
            run_id       TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
            sharpe       DOUBLE PRECISION,
            sortino      DOUBLE PRECISION,
            cagr         DOUBLE PRECISION,
            calmar       DOUBLE PRECISION,
            max_drawdown DOUBLE PRECISION,
            win_rate     DOUBLE PRECISION,
            total_return DOUBLE PRECISION,
            extra        JSONB
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS equity CASCADE")
    op.execute("DROP TABLE IF EXISTS trades CASCADE")
    op.execute("DROP TABLE IF EXISTS forecasts CASCADE")
    op.execute("DROP TABLE IF EXISTS prices CASCADE")
    op.execute("DROP TABLE IF EXISTS runs CASCADE")
    op.execute("DROP TABLE IF EXISTS models CASCADE")
    op.execute("DROP TABLE IF EXISTS tickers CASCADE")
