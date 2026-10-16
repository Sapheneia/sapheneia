"""Reusable slowapi rate limiter for services that did not have one.

``forecast`` and ``trading`` already establish this pattern. The orchestrator,
data, and metrics services shipped without it, so their Bearer validation had no
lockout — and the orchestrator's write endpoints (``DELETE /runs/{id}``,
``DELETE /cache``, batch submit) are the most expensive surface in the system.

This is a factory rather than a module-level singleton so each service gets its
own limiter with its own limits.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

logger = logging.getLogger("sapheneia.rate_limit")


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    """Starlette types handlers as ``(Request, Exception)``; slowapi only ever
    dispatches ``RateLimitExceeded`` here."""
    logger.warning(
        "Rate limit exceeded for %s on %s", get_remote_address(request), request.url.path
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
        },
        headers=getattr(exc, "headers", {}) or {},
    )


def make_limiter(*, default_limit: str = "120/minute", enabled: bool = True) -> Limiter:
    return Limiter(
        key_func=get_remote_address,
        default_limits=[default_limit],
        enabled=enabled,
        headers_enabled=True,
    )


def install(app: FastAPI, limiter: Limiter) -> Limiter:
    """Attach a limiter, its middleware, and the 429 handler to an app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    return limiter
