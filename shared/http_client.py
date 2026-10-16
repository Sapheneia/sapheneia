"""Shared async HTTP client base for every service-to-service call.

Consolidates what used to be eight hand-rolled copies (four orchestrator
clients + four MCP passthroughs) of the same three concerns: base-URL
normalisation, bearer-header assembly, and ``X-Request-ID`` propagation. The
MCP copies had drifted — they never propagated the request ID at all, so
passthrough calls were untraceable.
"""

from __future__ import annotations

from typing import Any

import httpx


class BaseHttpClient:
    """Thin wrapper over ``httpx.AsyncClient`` with consistent auth + tracing."""

    def __init__(self, base_url: str, *, api_key: str = "", timeout: float = 30.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._api_key = api_key

    @property
    def base_url(self) -> str:
        return self._base

    def headers(self, request_id: str | None = None) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        if request_id:
            h["X-Request-ID"] = request_id
        return h

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        request_id: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Perform a request and return the decoded JSON body.

        The return type is ``Any`` rather than ``dict`` because several
        endpoints legitimately return a JSON *array* (e.g. the orchestrator's
        run listings).
        """
        url = f"{(base_url or self._base).rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=timeout or self._timeout) as client:
            r = await client.request(
                method,
                url,
                json=json,
                params=params,
                headers=self.headers(request_id),
            )
            r.raise_for_status()
            return r.json()

    async def get(self, path: str, **kw: Any) -> Any:
        return await self.request("GET", path, **kw)

    async def post(self, path: str, **kw: Any) -> Any:
        return await self.request("POST", path, **kw)

    async def delete(self, path: str, **kw: Any) -> Any:
        return await self.request("DELETE", path, **kw)
