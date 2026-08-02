"""UTC normalisation for everything that touches a ``TIMESTAMPTZ`` column.

asyncpg's ``timestamptz`` codec calls ``obj.astimezone(utc)`` on the value it
is given. Python treats a *naive* datetime in that call as wall-clock time in
the host's local zone, so binding a naive datetime makes the stored instant a
function of whichever machine wrote it. That is unacceptable here: the
no-look-ahead guarantee is enforced by a SQL ``time <= $n`` clamp, and the
clamp is only correct if both sides were computed in the same zone.

Every datetime handed to the database goes through this module.
"""

from __future__ import annotations

from datetime import UTC, date, datetime


def ensure_utc(value: datetime) -> datetime:
    """Return ``value`` as a UTC-aware datetime.

    A naive input is *interpreted* as UTC (not converted from local time),
    which is the correct reading for the data this system handles: yfinance
    daily bars and evaluation-window boundaries are calendar dates, not
    local wall-clock instants.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def day_start(d: date) -> datetime:
    """Midnight UTC on ``d``."""
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def day_end(d: date) -> datetime:
    """The last representable instant on ``d``, in UTC."""
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=UTC)


def to_utc_datetime(value: object) -> datetime:
    """Coerce a datetime / date / ISO-8601 string into a UTC-aware datetime."""
    if isinstance(value, datetime):
        return ensure_utc(value)
    if isinstance(value, date):
        return day_start(value)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return ensure_utc(parsed)


def to_utc_date(value: object) -> date:
    """Coerce a datetime / date / ISO-8601 string into a UTC calendar date."""
    return to_utc_datetime(value).date()
