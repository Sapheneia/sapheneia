"""Alembic environment for Sapheneia TimescaleDB migrations.

Uses SQLAlchemy only as the migration runner. Application code uses asyncpg
directly via shared/db.py. No SQLAlchemy ORM or models are involved.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make repo root importable so we can use shared/db.py if needed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_dsn() -> str:
    """Prefer DATABASE_URL/TIMESCALEDB_* env vars over alembic.ini default."""
    if env_url := os.getenv("DATABASE_URL"):
        return env_url
    host = os.getenv("TIMESCALEDB_HOST", "localhost")
    port = os.getenv("TIMESCALEDB_PORT", "5432")
    user = os.getenv("TIMESCALEDB_USER", "sapheneia")
    password = os.getenv("TIMESCALEDB_PASSWORD", "sapheneia")
    db = os.getenv("TIMESCALEDB_DB", "sapheneia")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


config.set_main_option("sqlalchemy.url", _resolve_dsn())


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
