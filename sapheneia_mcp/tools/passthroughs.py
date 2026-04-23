"""Direct passthroughs to leaf services (data, forecast, trading, metrics).

These exist for ad-hoc agent inspection and debugging. The skill prefers the
composite tools (run_simulation, etc.) for normal workflows.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import httpx

from ..config import settings


async def fetch_prices(
    ticker: str,
    start: str,
    end: str,
    end_date: Optional[str] = None,
    interval: str = "1d",
) -> dict:
    params = {"ticker": ticker, "start": start, "end": end, "interval": interval}
    if end_date:
        params["end_date"] = end_date
    headers = {"Authorization": f"Bearer {settings.DATA_API_KEY}"} if settings.DATA_API_KEY else {}
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        r = await client.get(f"{settings.DATA_URL}/v1/data/prices", params=params, headers=headers)
        r.raise_for_status()
        return r.json()


async def forecast(
    model_id: str,
    context: list[float],
    prediction_length: int,
    num_samples: int = 20,
) -> dict:
    family = "chronos" if "chronos" in model_id.lower() else "timesfm20"
    body: dict[str, Any] = {
        "context": context,
        "prediction_length": prediction_length,
        "num_samples": num_samples,
    }
    if family == "chronos":
        body["model_variant"] = model_id
    else:
        body["checkpoint"] = model_id
    headers = {"Authorization": f"Bearer {settings.FORECAST_API_KEY}"} if settings.FORECAST_API_KEY else {}
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        r = await client.post(
            f"{settings.FORECAST_URL}/forecast/v1/{family}/inference",
            json=body,
            headers=headers,
        )
        r.raise_for_status()
        return r.json()


async def execute_trade(
    strategy_type: str,
    forecast_price: float,
    current_price: float,
    current_position: float,
    available_cash: float,
    initial_capital: float,
    params: Optional[dict[str, Any]] = None,
) -> dict:
    body = {
        "strategy_type": strategy_type,
        "forecast_price": forecast_price,
        "current_price": current_price,
        "current_position": current_position,
        "available_cash": available_cash,
        "initial_capital": initial_capital,
        **(params or {}),
    }
    headers = {"Authorization": f"Bearer {settings.TRADING_API_KEY}"} if settings.TRADING_API_KEY else {}
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        r = await client.post(f"{settings.TRADING_URL}/trading/execute", json=body, headers=headers)
        r.raise_for_status()
        return r.json()


async def compute_metrics(returns: list[float], metric: str = "performance") -> dict:
    headers = {"Authorization": f"Bearer {settings.METRICS_API_KEY}"} if settings.METRICS_API_KEY else {}
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        r = await client.post(
            f"{settings.METRICS_URL}/metrics/v1/compute",
            json={"returns": returns, "metric": metric},
            headers=headers,
        )
        r.raise_for_status()
        return r.json()
