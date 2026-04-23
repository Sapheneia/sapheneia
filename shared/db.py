"""TimescaleDB connection helpers shared across services.

All services that talk to TimescaleDB go through this module so that
DSN construction, pool sizing, and lifecycle are consistent.
"""

from __future__ import annotations

import os
from typing import Optional

import asyncpg


def dsn_from_env() -> str:
    """Construct a Postgres DSN from environment variables.

    Reads:
      TIMESCALEDB_HOST     (default: localhost)
      TIMESCALEDB_PORT     (default: 5432)
      TIMESCALEDB_USER     (default: sapheneia)
      TIMESCALEDB_PASSWORD (default: sapheneia)
      TIMESCALEDB_DB       (default: sapheneia)
    """
    host = os.getenv("TIMESCALEDB_HOST", "localhost")
    port = os.getenv("TIMESCALEDB_PORT", "5432")
    user = os.getenv("TIMESCALEDB_USER", "sapheneia")
    password = os.getenv("TIMESCALEDB_PASSWORD", "sapheneia")
    db = os.getenv("TIMESCALEDB_DB", "sapheneia")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def create_pool(
    dsn: Optional[str] = None,
    min_size: int = 2,
    max_size: int = 10,
) -> asyncpg.Pool:
    """Create an asyncpg connection pool. Caller owns lifecycle."""
    return await asyncpg.create_pool(
        dsn or dsn_from_env(),
        min_size=min_size,
        max_size=max_size,
        command_timeout=60.0,
    )
