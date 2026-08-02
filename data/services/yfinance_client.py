"""Thin async wrapper around the synchronous ``yfinance`` library.

We isolate yfinance behind a single function so unit tests can monkeypatch it
easily and the rest of the service stays purely async.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from datetime import date, datetime

from shared.timeutils import ensure_utc

logger = logging.getLogger(__name__)


def _fetch_sync(ticker: str, start: date, end: date, interval: str) -> list[dict]:
    """Synchronous yfinance fetch returning normalized dict rows.

    Imported lazily so the module can be imported without yfinance installed
    (e.g., in unit tests that monkeypatch this function).
    """
    import yfinance as yf  # type: ignore[import-untyped]

    df = yf.download(
        tickers=ticker,
        start=start.isoformat(),
        end=end.isoformat(),
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        return []

    if hasattr(df.columns, "get_level_values") and df.columns.nlevels > 1:
        try:
            df = df.xs(ticker, axis=1, level=1)
        except (KeyError, ValueError):
            df.columns = ["_".join(filter(None, map(str, c))) for c in df.columns]

    rows: list[dict] = []
    for idx, row in df.iterrows():
        raw_ts = (
            idx.to_pydatetime()
            if hasattr(idx, "to_pydatetime")
            else datetime.fromisoformat(str(idx))
        )
        # yfinance daily bars come back tz-naive. Stamp them UTC here rather
        # than letting asyncpg reinterpret them as host-local wall clock, which
        # would shift a bar onto a neighbouring calendar day depending on where
        # the ingest ran.
        ts = ensure_utc(raw_ts)
        rows.append(
            {
                "time": ts,
                "ticker": ticker,
                "open": _safe(row, "Open"),
                "high": _safe(row, "High"),
                "low": _safe(row, "Low"),
                "close": _safe(row, "Close"),
                "adj_close": _safe(row, "Adj Close"),
                "volume": _safe_int(row, "Volume"),
            }
        )
    return rows


def _safe(row, key: str) -> float | None:
    try:
        v = row[key]
    except (KeyError, IndexError):
        return None
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN check
        return None
    return f


def _safe_int(row, key: str) -> int | None:
    f = _safe(row, key)
    return None if f is None else int(f)


async def fetch(ticker: str, start: date, end: date, interval: str = "1d") -> list[dict]:
    """Async-safe ticker fetch."""
    return await asyncio.to_thread(_fetch_sync, ticker, start, end, interval)


async def fetch_many(
    tickers: Iterable[str],
    start: date,
    end: date,
    interval: str,
    semaphore: asyncio.Semaphore,
) -> dict[str, list[dict]]:
    """Fetch multiple tickers concurrently, capped by ``semaphore``."""

    async def _one(t: str) -> tuple[str, list[dict]]:
        async with semaphore:
            try:
                rows = await fetch(t, start, end, interval)
            except Exception as exc:  # surface to caller, don't crash the batch
                logger.warning("yfinance fetch failed for %s: %s", t, exc)
                rows = []
            return t, rows

    results = await asyncio.gather(*(_one(t) for t in tickers))
    return dict(results)
