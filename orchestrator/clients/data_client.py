"""HTTP client for the data service."""

from __future__ import annotations

from datetime import date

import httpx


class DataClient:
    def __init__(self, base_url: str, *, api_key: str = "", timeout: float = 60.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def get_prices(
        self,
        ticker: str,
        start: date,
        end: date,
        interval: str = "1d",
        end_date: date | None = None,
        request_id: str | None = None,
    ) -> list[dict]:
        params = {
            "ticker": ticker,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "interval": interval,
        }
        if end_date is not None:
            params["end_date"] = end_date.isoformat()
        headers = dict(self._headers)
        if request_id:
            headers["X-Request-ID"] = request_id
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(f"{self._base}/v1/data/prices", params=params, headers=headers)
            r.raise_for_status()
            return r.json().get("bars", [])
