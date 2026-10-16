"""HTTP client for the trading service."""

from __future__ import annotations

from typing import Any

from shared.http_client import BaseHttpClient


class TradingClient(BaseHttpClient):
    def __init__(self, base_url: str, *, api_key: str = "", timeout: float = 30.0):
        super().__init__(base_url, api_key=api_key, timeout=timeout)

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
        return await self.post("/trading/execute", json=body, request_id=request_id)
