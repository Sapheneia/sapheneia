"""Smoke test: alembic migrations apply cleanly to a fresh TimescaleDB.

Marked as ``integration`` because it requires Docker to spin up a TimescaleDB
container via testcontainers. Skipped in pure-unit runs.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "migrations" / "alembic.ini"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def timescaledb_url() -> str:
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers[postgres] not installed")

    image = "timescale/timescaledb:latest-pg16"
    container = PostgresContainer(
        image=image,
        username="sapheneia",
        password="sapheneia",
        dbname="sapheneia",
    )
    container.start()
    try:
        url = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        yield url
    finally:
        container.stop()


def test_migrations_upgrade_and_downgrade(timescaledb_url: str) -> None:
    env = {**os.environ, "DATABASE_URL": timescaledb_url}

    up = subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert up.returncode == 0, f"alembic upgrade failed: {up.stdout}\n{up.stderr}"

    down = subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), "downgrade", "base"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert down.returncode == 0, f"alembic downgrade failed: {down.stdout}\n{down.stderr}"
