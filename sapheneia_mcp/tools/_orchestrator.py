"""Shared orchestrator HTTP client for the MCP tools.

``runs.py`` and ``cache.py`` each carried their own header helper — one named
``_orchestrator_headers``, the other ``_headers`` — doing identical work. One
client, one name.
"""

from __future__ import annotations

from shared.http_client import BaseHttpClient

from ..config import settings


def orchestrator_client() -> BaseHttpClient:
    return BaseHttpClient(
        settings.ORCHESTRATOR_URL,
        api_key=settings.ORCHESTRATOR_API_KEY,
        timeout=settings.HTTP_TIMEOUT,
    )
