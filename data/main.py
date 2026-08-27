"""Sapheneia data service — FastAPI entry point."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Path bootstrap so `import shared` works when run inside Docker
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import db as shared_db  # noqa: E402
from shared.errors import register_error_handlers  # noqa: E402
from shared.rate_limit import install as install_rate_limit  # noqa: E402
from shared.rate_limit import make_limiter  # noqa: E402

from .core.config import settings  # noqa: E402
from .routes.endpoints import router as data_router  # noqa: E402
from .services.prices_repo import PricesRepo  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
)
logger = logging.getLogger("sapheneia.data")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting sapheneia-data v2")
    pool = await shared_db.create_pool()
    repo = PricesRepo(pool, fetch_concurrency=settings.YFINANCE_MAX_CONCURRENCY)
    app.state.pool = pool
    app.state.prices_repo = repo
    try:
        yield
    finally:
        await pool.close()
        logger.info("sapheneia-data shutdown complete")


app = FastAPI(
    title="Sapheneia Data API",
    version="2.0.0",
    description="Yahoo Finance + TimescaleDB price cache",
    lifespan=lifespan,
)

register_error_handlers(app)
install_rate_limit(app, make_limiter(default_limit=f"{settings.RATE_LIMIT_PER_MINUTE}/minute"))
app.include_router(data_router)


@app.get("/")
async def root() -> dict:
    return {"service": "sapheneia-data", "version": "2.0.0"}


@app.get("/health")
async def health() -> dict:
    pool = app.state.pool
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("db health probe failed: %s", exc)
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}
