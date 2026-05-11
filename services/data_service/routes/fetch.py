from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple

from fastapi import APIRouter, HTTPException, Request, status

from ..schemas import DataFetchRequest, DataFetchResponse
from ..yahoo import YahooClient, YahooError, parse_start_date, normalize_ticker_tag

logger = logging.getLogger(__name__)
router = APIRouter()


async def _fetch_one(
    ticker: str,
    request_start_date: str,
    interval: str,
    yahoo: YahooClient,
    influx,
) -> Tuple[str, str]:
    default_start = parse_start_date(request_start_date)

    latest = await influx.latest_stock_timestamp(ticker)
    if latest is not None:
        # +1 day to avoid duplicates (matches Go)
        candidate = latest + timedelta(days=1)
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=timezone.utc)
        if default_start.tzinfo is None:
            default_start = default_start.replace(tzinfo=timezone.utc)
        start = candidate if candidate > default_start else default_start
    else:
        start = default_start

    end = datetime.now(timezone.utc)

    try:
        bars = await yahoo.fetch_chart(ticker, start, end, interval)
    except YahooError as e:
        logger.error("yahoo fetch failed", extra={"ticker": ticker, "error": str(e)})
        return ticker, f"Error: {e}"
    except Exception as e:
        logger.exception("yahoo fetch crashed", extra={"ticker": ticker})
        return ticker, f"Error: {e}"

    if not bars:
        return ticker, "No new data"

    try:
        n = await influx.write_stock_bars(normalize_ticker_tag(ticker), bars)
    except Exception as e:
        logger.exception("influx write failed", extra={"ticker": ticker})
        return ticker, f"Error: {e}"

    return ticker, f"{n} points written"


@router.post("/v1/data/fetch", response_model=DataFetchResponse)
async def handle_fetch(req: DataFetchRequest, request: Request) -> DataFetchResponse:
    if not req.names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tickers provided")

    interval = req.interval or "1d"

    yahoo: YahooClient = request.app.state.yahoo
    influx = request.app.state.influx
    concurrency: int = request.app.state.settings.fetch_concurrency

    sem = asyncio.Semaphore(concurrency)

    async def _bounded(t: str) -> Tuple[str, str]:
        async with sem:
            return await _fetch_one(t, req.start_date, interval, yahoo, influx)

    results = await asyncio.gather(*(_bounded(t) for t in req.names))
    details = {ticker: msg for ticker, msg in results}

    return DataFetchResponse(
        status="success",
        message=f"Data fetch cycle completed for {len(req.names)} tickers",
        details=details,
    )
