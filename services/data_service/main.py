from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from .config import load_settings
from .influx import InfluxStore
from .routes import fetch, query, write_results
from .yahoo import YahooClient


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    settings = load_settings()
    app.state.settings = settings

    influx = InfluxStore(
        url=settings.influx_url,
        token=settings.influx_token,
        org=settings.influx_org,
        bucket=settings.influx_bucket,
    )
    logging.info("Waiting for InfluxDB to be ready...")
    ready = await influx.wait_until_ready(
        attempts=settings.influx_ready_attempts,
        delay_s=settings.influx_ready_delay_s,
    )
    if not ready:
        influx.close()
        raise RuntimeError("Failed to connect to InfluxDB after all retries.")
    logging.info("Successfully connected to InfluxDB.")
    app.state.influx = influx

    http = httpx.AsyncClient(timeout=settings.yahoo_timeout_s)
    app.state.http = http
    app.state.yahoo = YahooClient(http=http, user_agent=settings.yahoo_user_agent)

    try:
        yield
    finally:
        await http.aclose()
        influx.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Sapheneia Finance Data Service", version="2.0.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(fetch.router)
    app.include_router(query.router)
    app.include_router(write_results.router)
    return app


app = create_app()
