"""Tests for shared DSN construction, the production key guard, and timeutils."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from shared.db import dsn_from_env
from shared.service_config import validate_api_key
from shared.timeutils import day_end, day_start, ensure_utc, to_utc_date, to_utc_datetime

DB_VARS = (
    "TIMESCALEDB_HOST",
    "TIMESCALEDB_PORT",
    "TIMESCALEDB_USER",
    "TIMESCALEDB_PASSWORD",
    "TIMESCALEDB_DB",
)


@pytest.fixture
def clean_env(monkeypatch):
    for var in DB_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


# --- dsn_from_env ---------------------------------------------------------


def test_dsn_defaults(clean_env) -> None:
    assert dsn_from_env() == "postgresql://sapheneia:sapheneia@localhost:5432/sapheneia"


def test_dsn_reads_every_variable(clean_env) -> None:
    for var, value in zip(DB_VARS, ["db.internal", "6543", "u", "p", "warehouse"], strict=True):
        clean_env.setenv(var, value)
    assert dsn_from_env() == "postgresql://u:p@db.internal:6543/warehouse"


def test_dsn_percent_encodes_special_characters(clean_env) -> None:
    """An unescaped '@' in a password re-splits the userinfo/host boundary.

    Without encoding, the pool would dial `evil.example.com` instead of the
    configured host — the exact failure you hit the first time you replace the
    default password with a strong generated one.
    """
    clean_env.setenv("TIMESCALEDB_PASSWORD", "p@ss/w#rd:1")
    clean_env.setenv("TIMESCALEDB_HOST", "db.internal")
    dsn = dsn_from_env()
    assert "p%40ss%2Fw%23rd%3A1" in dsn
    assert dsn.endswith("@db.internal:5432/sapheneia")
    assert dsn.count("@") == 1


# --- validate_api_key -----------------------------------------------------


@pytest.mark.parametrize("value", ["", "change_me", "change_me_in_production_abc123"])
def test_placeholder_key_fails_in_production(value) -> None:
    with pytest.raises(ValueError, match="SECURITY"):
        validate_api_key(value, environment="production", field_name="X_API_KEY")


@pytest.mark.parametrize("value", ["", "change_me"])
def test_placeholder_key_only_warns_outside_production(value) -> None:
    assert validate_api_key(value, environment="development", field_name="X_API_KEY") == value


def test_short_key_fails_in_production() -> None:
    with pytest.raises(ValueError, match="32"):
        validate_api_key("tooshort", environment="production", field_name="X_API_KEY")


def test_strong_key_passes_in_production() -> None:
    key = "s" * 48
    assert validate_api_key(key, environment="production", field_name="X_API_KEY") == key


def test_key_containing_hash_is_rejected_in_production() -> None:
    """Catches the .env inline-comment trap.

    `KEY=   # comment` parses the comment text as the value, which silently
    ENABLES auth using a string published in the repository.
    """
    with pytest.raises(ValueError, match="inline .env comment"):
        validate_api_key("# empty disables auth", environment="production", field_name="X_API_KEY")


def test_empty_optional_key_is_accepted_in_production() -> None:
    assert validate_api_key("", environment="production", field_name="X", required=False) == ""


# --- timeutils ------------------------------------------------------------


def test_ensure_utc_treats_naive_as_utc_not_local() -> None:
    naive = datetime(2024, 1, 1, 12, 0, 0)
    assert ensure_utc(naive) == datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_ensure_utc_converts_an_offset_aware_datetime() -> None:
    aware = datetime(2024, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    assert ensure_utc(aware) == datetime(2024, 1, 1, 7, 0, tzinfo=UTC)


def test_day_boundaries_are_utc_aware() -> None:
    d = date(2024, 6, 15)
    assert day_start(d) == datetime(2024, 6, 15, 0, 0, tzinfo=UTC)
    assert day_end(d) == datetime(2024, 6, 15, 23, 59, 59, 999999, tzinfo=UTC)
    assert day_start(d).tzinfo is not None and day_end(d).tzinfo is not None


@pytest.mark.parametrize(
    "value",
    [datetime(2024, 5, 4), date(2024, 5, 4), "2024-05-04", "2024-05-04T00:00:00Z"],
)
def test_to_utc_datetime_accepts_the_shapes_the_data_service_returns(value) -> None:
    out = to_utc_datetime(value)
    assert out.tzinfo is not None
    assert to_utc_date(value) == date(2024, 5, 4)
