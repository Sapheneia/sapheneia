"""Sapheneia orchestrator service — FastAPI entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import db as shared_db  # noqa: E402
from shared.errors import register_error_handlers  # noqa: E402

from .clients.data_client import DataClient  # noqa: E402
from .clients.forecast_client import ForecastClient  # noqa: E402
from .clients.metrics_client import MetricsClient  # noqa: E402
from .clients.trading_client import TradingClient  # noqa: E402
from .core.config import settings  # noqa: E402
from .repositories.forecasts_repo import ForecastsRepository  # noqa: E402
from .repositories.runs_repo import MetricsRepository, RunsRepository  # noqa: E402
from .repositories.trades_repo import EquityRepository, TradesRepository  # noqa: E402
from .routes.endpoints import router as orch_router  # noqa: E402
from .services.inner_loop import InnerLoop  # noqa: E402
from .services.reconciler import heartbeat_reconciler_loop  # noqa: E402
from .services.runs_service import RunsService  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s",
)
logger = logging.getLogger("sapheneia.orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting orchestrator")
    pool = await shared_db.create_pool()

    runs_repo = RunsRepository(pool)
    forecasts_repo = ForecastsRepository(pool)
    trades_repo = TradesRepository(pool)
    equity_repo = EquityRepository(pool)
    metrics_repo = MetricsRepository(pool)

    data_client = DataClient(
        settings.DATA_SERVICE_URL, api_key=settings.DATA_API_KEY, timeout=settings.DATA_TIMEOUT
    )
    forecast_client = ForecastClient(
        settings.FORECAST_SERVICE_URL,
        api_key=settings.FORECAST_API_KEY,
        timeout=settings.FORECAST_TIMEOUT,
    )
    trading_client = TradingClient(
        settings.TRADING_SERVICE_URL,
        api_key=settings.TRADING_API_KEY,
        timeout=settings.TRADING_TIMEOUT,
    )
    metrics_client = MetricsClient(
        settings.METRICS_SERVICE_URL,
        api_key=settings.METRICS_API_KEY,
        timeout=settings.METRICS_TIMEOUT,
    )

    per_model_semaphores: dict[str, asyncio.Semaphore] = {}
    inner = InnerLoop(
        data_client=data_client,
        forecast_client=forecast_client,
        trading_client=trading_client,
        metrics_client=metrics_client,
        runs_repo=runs_repo,
        forecasts_repo=forecasts_repo,
        trades_repo=trades_repo,
        equity_repo=equity_repo,
        metrics_repo=metrics_repo,
        per_model_semaphores=per_model_semaphores,
    )
    runs_service = RunsService(
        runs_repo=runs_repo,
        inner_loop=inner,
        max_concurrent_runs=settings.MAX_CONCURRENT_RUNS,
    )

    app.state.pool = pool
    app.state.runs_repo = runs_repo
    app.state.forecasts_repo = forecasts_repo
    app.state.runs_service = runs_service

    reconciler_task = asyncio.create_task(
        heartbeat_reconciler_loop(
            runs_repo, settings.HEARTBEAT_INTERVAL, settings.HEARTBEAT_STALE_AFTER
        )
    )

    try:
        yield
    finally:
        reconciler_task.cancel()
        try:
            await reconciler_task
        except asyncio.CancelledError:
            pass
        await pool.close()
        logger.info("Orchestrator shutdown complete")


app = FastAPI(
    title="Sapheneia Orchestrator",
    version="2.0.0",
    description="Sole writer of run-state to TimescaleDB",
    lifespan=lifespan,
)
register_error_handlers(app)
app.include_router(orch_router)


@app.get("/")
async def root() -> dict:
    return {"service": "sapheneia-orchestrator", "version": "2.0.0"}


@app.get("/health")
async def health() -> dict:
    pool = app.state.pool
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        ok = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("orchestrator db probe failed: %s", exc)
        ok = False
    return {"status": "ok" if ok else "degraded", "db": ok}
