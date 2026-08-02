"""HTTP client for the metrics service."""

from __future__ import annotations

from shared.http_client import BaseHttpClient


class MetricsClient(BaseHttpClient):
    def __init__(self, base_url: str, *, api_key: str = "", timeout: float = 30.0):
        super().__init__(base_url, api_key=api_key, timeout=timeout)

    async def compute(
        self,
        *,
        returns: list[float],
        metric: str = "performance",
        request_id: str | None = None,
    ) -> dict:
        return await self.post(
            "/metrics/v1/compute",
            json={"returns": returns, "metric": metric},
            request_id=request_id,
        )
