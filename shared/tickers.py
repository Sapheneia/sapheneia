"""Shared ticker-registration SQL.

`data` owns the `tickers` table (§4.3), but the orchestrator must pre-register a
ticker so `runs.ticker`'s foreign key is satisfiable at submit time — before the
data service has ever been asked for prices. Two writers is a deliberate,
narrow exception; sharing the statement keeps them from drifting.

`asset_class` is currently always the placeholder below: nothing classifies
tickers yet, and `ON CONFLICT DO NOTHING` means whichever writer arrives first
wins and later writers cannot correct it. Treat the column as unpopulated until
a real classification source exists.
"""

from __future__ import annotations

UNKNOWN_ASSET_CLASS = "unknown"

ENSURE_TICKER_SQL = """
INSERT INTO tickers (ticker, asset_class)
VALUES ($1, $2)
ON CONFLICT (ticker) DO NOTHING
"""
