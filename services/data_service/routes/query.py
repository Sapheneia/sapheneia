from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from ..schemas import DataPoint, DataQueryRequest, DataQueryResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/v1/data/query", response_model=DataQueryResponse)
async def handle_query(req: DataQueryRequest, request: Request) -> DataQueryResponse:
    if not req.ticker:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ticker is required")

    days = req.days if req.days > 0 else 252  # Default 1 year of trading days

    influx = request.app.state.influx
    try:
        rows = await influx.query_stock_history(req.ticker, days, req.end_date or None)
    except Exception as e:
        logger.exception("query failed", extra={"ticker": req.ticker})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Query failed", "details": str(e)},
        )

    points = [
        DataPoint(
            time=row["time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            adj_close=row["adj_close"],
        )
        for row in rows
    ]
    return DataQueryResponse(ticker=req.ticker, data=points, count=len(points))
