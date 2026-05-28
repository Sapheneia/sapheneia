"""HTTP client for the trading service."""

from __future__ import annotations

from typing import Any

import httpx


class TradingClient:
    def __init__(self, base_url: str, *, api_key: str = "", timeout: float = 30.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def execute(
        self,
        *,
        strategy_type: str,
        params: dict[str, Any],
        forecast_price: float,
        current_price: float,
        current_position: float,
        available_cash: float,
        initial_capital: float,
        request_id: str | None = None,
    ) -> dict:
        body = {
            "strategy_type": strategy_type,
            "forecast_price": forecast_price,
            "current_price": current_price,
            "current_position": current_position,
            "available_cash": available_cash,
            "initial_capital": initial_capital,
            **params,
        }
        headers = dict(self._headers)
        if request_id:
            headers["X-Request-ID"] = request_id
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(f"{self._base}/trading/execute", json=body, headers=headers)
            r.raise_for_status()
            return r.json()
