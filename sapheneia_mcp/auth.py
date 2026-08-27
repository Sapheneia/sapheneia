"""Bearer-token enforcement for the MCP server's HTTP/SSE transport.

Why this is not optional
------------------------
This process holds a bearer key for *every* downstream service (orchestrator,
data, forecast, trading, metrics). An unauthenticated listener on it is a
confused deputy: any network peer could call ``delete_run``, ``delete_cache``,
or ``run_simulation`` with no credential, and the MCP would faithfully re-sign
those calls with real service keys — defeating the auth on all five services at
once.

``SAPHENEIA_MCP_TOKEN`` was previously declared in config, wired in
docker-compose, and documented in ``.env.template``, but never actually read.
An operator reading any of those three would reasonably conclude auth was on.
"""

from __future__ import annotations

import logging
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

logger = logging.getLogger("sapheneia.mcp.auth")

#: Unauthenticated liveness probes. Everything else requires the token.
PUBLIC_PATHS = frozenset({"/health"})


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Reject any request whose ``Authorization: Bearer`` does not match."""

    def __init__(self, app: ASGIApp, *, token: str):
        super().__init__(app)
        if not token:
            raise ValueError("BearerTokenMiddleware requires a non-empty token")
        self._token = token

    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")
        scheme, _, credential = header.partition(" ")
        if scheme.lower() != "bearer" or not credential:
            logger.warning(
                "MCP auth failed (missing bearer token) from %s",
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                {"detail": "Missing Bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not secrets.compare_digest(credential, self._token):
            logger.warning(
                "MCP auth failed (invalid token) from %s",
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                {"detail": "Invalid token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
