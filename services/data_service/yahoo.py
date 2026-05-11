"""Yahoo Finance v8 chart API client."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


class YahooError(Exception):
    pass


def parse_start_date(value: str) -> datetime:
    """Match Go service: try YYYY-MM-DD, then YYYYMMDD, fall back to now-1y.

    The Go fallback returns a tz-naive value in local time. We return UTC to
    keep behavior reproducible across hosts; the only consumer compares to
    `now()` and converts to a unix timestamp, so tz consistency is what matters.
    """
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return datetime.now(timezone.utc) - timedelta(days=365)


def normalize_ticker_tag(ticker: str) -> str:
    """Match Go: strings.ReplaceAll(ticker, "-USD", "USDT")."""
    return ticker.replace("-USD", "USDT")


class YahooClient:
    def __init__(self, http: httpx.AsyncClient, user_agent: str):
        self._http = http
        self._headers = {"User-Agent": user_agent}

    async def fetch_chart(
        self, ticker: str, start: datetime, end: datetime, interval: str
    ) -> List[dict]:
        """Return one bar per element: {time, open, high, low, close, adj_close, volume}.

        Bars where any field is missing are skipped (matches Go behavior).
        Returns [] if start >= end (start in the future).
        """
        if start >= end:
            return []

        params = {
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "interval": interval,
            "events": "history",
        }
        url = YAHOO_URL.format(ticker=ticker)

        resp = await self._http.get(url, params=params, headers=self._headers)
        if resp.status_code != 200:
            raise YahooError(f"Yahoo API returned status {resp.status_code} {resp.reason_phrase}")

        payload = resp.json()
        chart = payload.get("chart") or {}
        if chart.get("error") is not None:
            raise YahooError(f"Yahoo API error: {chart['error']}")
        results = chart.get("result") or []
        if not results:
            raise YahooError(f"no results in Yahoo response for ticker {ticker}")

        res = results[0]
        timestamps = res.get("timestamp") or []
        indicators = res.get("indicators") or {}
        quote_list = indicators.get("quote") or []
        adj_list = indicators.get("adjclose") or []

        if not quote_list or not adj_list:
            raise YahooError(f"incomplete indicators in Yahoo response for ticker {ticker}")

        quote = quote_list[0]
        adj = adj_list[0].get("adjclose") or []
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        bars: List[dict] = []
        for i, ts in enumerate(timestamps):
            if (
                i >= len(adj)
                or i >= len(opens)
                or i >= len(highs)
                or i >= len(lows)
                or i >= len(closes)
                or i >= len(volumes)
            ):
                logger.warning("skipping incomplete data point", extra={"ticker": ticker, "ts": ts})
                continue
            if any(v is None for v in (opens[i], highs[i], lows[i], closes[i], volumes[i], adj[i])):
                logger.warning("skipping null data point", extra={"ticker": ticker, "ts": ts})
                continue
            bars.append(
                {
                    "time": datetime.fromtimestamp(ts, tz=timezone.utc),
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(closes[i]),
                    "adj_close": float(adj[i]),
                    "volume": int(volumes[i]),
                }
            )
        return bars
