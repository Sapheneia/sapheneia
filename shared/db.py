"""TimescaleDB connection helpers shared across services.

All services that talk to TimescaleDB go through this module so that
DSN construction, pool sizing, and lifecycle are consistent.
"""

from __future__ import annotations

import os
from urllib.parse import quote

import asyncpg


def dsn_from_env() -> str:
    """Construct a Postgres DSN from environment variables.

    Reads:
      TIMESCALEDB_HOST     (default: localhost)
      TIMESCALEDB_PORT     (default: 5432)
      TIMESCALEDB_USER     (default: sapheneia)
      TIMESCALEDB_PASSWORD (default: sapheneia)
      TIMESCALEDB_DB       (default: sapheneia)

    User and password are percent-encoded. Without that, a password containing
    ``@`` re-splits the userinfo/host boundary and the pool silently dials an
    unintended host — which is exactly the failure mode you hit the first time
    you replace the default password with a strong generated one.
    """
    host = os.getenv("TIMESCALEDB_HOST", "localhost")
    port = os.getenv("TIMESCALEDB_PORT", "5432")
    user = quote(os.getenv("TIMESCALEDB_USER", "sapheneia"), safe="")
    password = quote(os.getenv("TIMESCALEDB_PASSWORD", "sapheneia"), safe="")
    db = quote(os.getenv("TIMESCALEDB_DB", "sapheneia"), safe="")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def create_pool(
    dsn: str | None = None,
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
