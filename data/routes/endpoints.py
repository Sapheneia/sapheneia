"""HTTP endpoints for the data service."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.security import get_api_key
from ..schemas.schema import (
    ALLOWED_INTERVALS,
    FetchRequest,
    FetchResponse,
    PriceBar,
    PricesQueryResponse,
)
from ..services.prices_repo import PricesRepo

router = APIRouter(prefix="/v1/data")


def _repo(request: Request) -> PricesRepo:
    repo: PricesRepo | None = getattr(request.app.state, "prices_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="prices repository not initialised")
    return repo


def _bar(record) -> PriceBar:
    return PriceBar(
        time=record["time"],
        ticker=record["ticker"],
        open=record["open"],
        high=record["high"],
        low=record["low"],
        close=record["close"],
        adj_close=record["adj_close"],
        volume=record["volume"],
    )


@router.post("/fetch", response_model=FetchResponse, dependencies=[Depends(get_api_key)])
async def fetch_prices(request: Request, body: FetchRequest) -> FetchResponse:
    """Bulk fetch prices for one or more tickers, populating the cache."""
    repo = _repo(request)
    by_ticker = await repo.read_many(body.tickers, body.start, body.end, body.interval)
    bars = [_bar(r) for rows in by_ticker.values() for r in rows]
    return FetchResponse(tickers=body.tickers, interval=body.interval, bars=bars)


@router.get("/prices", response_model=PricesQueryResponse, dependencies=[Depends(get_api_key)])
async def get_prices(
    request: Request,
    ticker: str = Query(min_length=1, max_length=20),
    start: date = Query(),
    end: date = Query(),
    end_date: date | None = Query(default=None, description="Backtest temporal upper bound"),
    interval: str = Query(default="1d"),
) -> PricesQueryResponse:
    """Query prices for one ticker, with optional ``end_date`` backtest bound."""
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"interval must be one of {sorted(ALLOWED_INTERVALS)}",
        )
    repo = _repo(request)
    rows = await repo.read_through(ticker, start, end, interval, end_date=end_date)
    return PricesQueryResponse(ticker=ticker, interval=interval, bars=[_bar(r) for r in rows])
