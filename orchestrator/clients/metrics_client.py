"""HTTP client for the metrics service."""

from __future__ import annotations

import httpx


class MetricsClient:
    def __init__(self, base_url: str, *, api_key: str = "", timeout: float = 30.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def compute(
        self,
        *,
        returns: list[float],
        metric: str = "performance",
        request_id: str | None = None,
    ) -> dict:
        headers = dict(self._headers)
        if request_id:
            headers["X-Request-ID"] = request_id
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(
                f"{self._base}/metrics/v1/compute",
                json={"returns": returns, "metric": metric},
                headers=headers,
            )
            r.raise_for_status()
            return r.json()
