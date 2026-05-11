from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from ..schemas import WriteResultsRequest, WriteResultsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/v1/data/write_results", response_model=WriteResultsResponse)
async def handle_write_results(
    req: WriteResultsRequest, request: Request
) -> WriteResultsResponse:
    if not req.run_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run_id is required")
    if not req.ticker:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ticker is required")
    if not req.results:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="results cannot be empty")

    influx = request.app.state.influx
    try:
        n = await influx.write_backtest_results(
            run_id=req.run_id,
            ticker=req.ticker,
            model=req.model,
            strategy=req.strategy,
            results=[r.model_dump() for r in req.results],
            metrics=req.metrics.model_dump(),
        )
    except Exception as e:
        logger.exception("influx write failed", extra={"run_id": req.run_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to write to InfluxDB", "details": str(e)},
        )

    return WriteResultsResponse(status="success", points_written=n, run_id=req.run_id)
