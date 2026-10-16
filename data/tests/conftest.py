"""Shared fixtures for the data service tests."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest


@pytest.fixture
def sample_yfinance_rows() -> list[dict]:
    """A canned yfinance result for a few business days."""
    return [
        {
            "time": datetime(2024, 1, 2),
            "ticker": "SPY",
            "open": 470.0,
            "high": 472.0,
            "low": 468.5,
            "close": 471.5,
            "adj_close": 471.5,
            "volume": 80_000_000,
        },
        {
            "time": datetime(2024, 1, 3),
            "ticker": "SPY",
            "open": 471.5,
            "high": 473.2,
            "low": 470.0,
            "close": 472.0,
            "adj_close": 472.0,
            "volume": 75_000_000,
        },
        {
            "time": datetime(2024, 1, 4),
            "ticker": "SPY",
            "open": 472.0,
            "high": 474.5,
            "low": 471.0,
            "close": 473.8,
            "adj_close": 473.8,
            "volume": 78_000_000,
        },
    ]


class FakeRecord(dict):
    """asyncpg.Record-like dict for unit tests."""

    def __getitem__(self, key: Any) -> Any:
        return super().__getitem__(key)
