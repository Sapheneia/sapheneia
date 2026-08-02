"""HTTP client for the data service."""

from __future__ import annotations

from datetime import date

from shared.http_client import BaseHttpClient


class DataClient(BaseHttpClient):
    def __init__(self, base_url: str, *, api_key: str = "", timeout: float = 60.0):
        super().__init__(base_url, api_key=api_key, timeout=timeout)

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
        payload = await self.get("/v1/data/prices", params=params, request_id=request_id)
        return payload.get("bars", [])
