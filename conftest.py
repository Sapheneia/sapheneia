"""Root pytest fixtures shared by every test package.

Provides one way to obtain a migrated TimescaleDB for integration tests, with
two sources so the same tests run everywhere:

1. **An externally provided database** (``TIMESCALEDB_HOST`` & friends). Used by
   the CI ``integration`` job's service container and by a developer who already
   has ``docker compose up timescaledb`` running.
2. **testcontainers**, which starts a throwaway TimescaleDB.

Previously both integration modules hard-coded source (2), so a CI job that
supplied a service container would silently start a *second* database inside the
runner and ignore the one it was given.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent
ALEMBIC_INI = REPO_ROOT / "migrations" / "alembic.ini"

#: Image pin shared with docker-compose.yml and the CI service container.
TIMESCALEDB_IMAGE = "timescale/timescaledb:2.17.2-pg16"


def _external_dsn() -> str | None:
    """Return a psycopg DSN for an externally provided DB, if one is reachable."""
    host = os.getenv("TIMESCALEDB_HOST")
    if not host:
        return None
    port = int(os.getenv("TIMESCALEDB_PORT", "5432"))
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError:
        return None
    user = os.getenv("TIMESCALEDB_USER", "sapheneia")
    password = os.getenv("TIMESCALEDB_PASSWORD", "sapheneia")
    db = os.getenv("TIMESCALEDB_DB", "sapheneia")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def _alembic(dsn: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": dsn},
        cwd=str(REPO_ROOT),
    )


@pytest.fixture(scope="session")
def timescaledb_psycopg_dsn() -> str:
    """A migrated TimescaleDB, as a ``postgresql+psycopg://`` DSN."""
    external = _external_dsn()
    if external:
        # Start from a clean schema so assertions don't inherit a stale shape
        # from a previous run against a long-lived database.
        _alembic(external, "downgrade", "base")
        result = _alembic(external, "upgrade", "head")
        if result.returncode != 0:
            pytest.fail(f"alembic upgrade failed on the external DB:\n{result.stderr}")
        yield external
        return

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("no external TIMESCALEDB_HOST and testcontainers is not installed")

    try:
        container = PostgresContainer(
            image=TIMESCALEDB_IMAGE,
            username="sapheneia",
            password="sapheneia",
            dbname="sapheneia",
        )
        container.start()
    except Exception as exc:  # noqa: BLE001 - docker unreachable is a skip, not a failure
        pytest.skip(f"could not start a TimescaleDB container: {exc}")

    try:
        dsn = container.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+psycopg://"
        )
        result = _alembic(dsn, "upgrade", "head")
        if result.returncode != 0:
            pytest.fail(f"alembic upgrade failed:\n{result.stderr}")
        yield dsn
    finally:
        container.stop()


@pytest.fixture(scope="session")
def timescaledb_asyncpg_dsn(timescaledb_psycopg_dsn: str) -> str:
    """The same database, as the ``postgresql://`` DSN asyncpg expects."""
    return timescaledb_psycopg_dsn.replace("postgresql+psycopg://", "postgresql://")
