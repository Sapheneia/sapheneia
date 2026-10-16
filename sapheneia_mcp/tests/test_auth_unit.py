"""Tests for MCP SSE bearer enforcement.

The token was declared in config, wired in docker-compose, and documented in
.env.template — but never read, so the SSE transport was fully open while
holding a key for every downstream service.
"""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from sapheneia_mcp.auth import BearerTokenMiddleware

TOKEN = "s3cret-token"


def _app(token: str = TOKEN) -> Starlette:
    async def ok(_request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/sse", ok), Route("/health", ok)])
    app.add_middleware(BearerTokenMiddleware, token=token)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app())


def test_rejects_a_request_with_no_authorization(client) -> None:
    r = client.get("/sse")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_rejects_a_wrong_token(client) -> None:
    assert client.get("/sse", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_rejects_a_non_bearer_scheme(client) -> None:
    assert client.get("/sse", headers={"Authorization": f"Basic {TOKEN}"}).status_code == 401


def test_rejects_a_bearer_with_no_credential(client) -> None:
    assert client.get("/sse", headers={"Authorization": "Bearer "}).status_code == 401


def test_accepts_the_configured_token(client) -> None:
    r = client.get("/sse", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_health_stays_reachable_for_container_probes(client) -> None:
    assert client.get("/health").status_code == 200


def test_middleware_refuses_to_be_built_without_a_token() -> None:
    # Constructed directly: Starlette's add_middleware defers instantiation to
    # app startup, so it would not surface the error here.
    async def _noop(_scope, _receive, _send):  # pragma: no cover
        return None

    with pytest.raises(ValueError, match="non-empty token"):
        BearerTokenMiddleware(_noop, token="")
