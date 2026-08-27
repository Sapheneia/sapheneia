"""Direct passthroughs to leaf services (data, forecast, trading, metrics).

These exist for ad-hoc agent inspection and debugging. The skill prefers the
composite tools (run_simulation, etc.) for normal workflows.

All four go through ``shared.http_client.BaseHttpClient`` so they get the same
bearer-header assembly and ``X-Request-ID`` propagation as the orchestrator's
clients — the hand-rolled versions here never propagated a request ID, which
made passthrough calls untraceable.
"""

from __future__ import annotations

from typing import Any

from shared.contracts import ForecastEnvelope, ForecastRequest
from shared.http_client import BaseHttpClient
from shared.model_registry import require as require_model

from ..config import settings


def _client(base_url: str, api_key: str) -> BaseHttpClient:
    return BaseHttpClient(base_url, api_key=api_key, timeout=settings.HTTP_TIMEOUT)


async def fetch_prices(
    ticker: str,
    start: str,
    end: str,
    end_date: str | None = None,
    interval: str = "1d",
    request_id: str | None = None,
) -> dict:
    params: dict[str, Any] = {
        "ticker": ticker,
        "start": start,
        "end": end,
        "interval": interval,
    }
    if end_date:
        params["end_date"] = end_date
    return await _client(settings.DATA_URL, settings.DATA_API_KEY).get(
        "/v1/data/prices", params=params, request_id=request_id
    )


async def forecast(
    model_id: str,
    context: list[float],
    prediction_length: int,
    num_samples: int = 20,
    request_id: str | None = None,
) -> dict:
    """Forecast via the model's own container.

    Resolves ``model_id`` through the shared registry rather than re-deriving
    the family from a substring check. The old inline check silently routed an
    unrecognised model to timesfm20; ``require`` raises instead, and the URL it
    returns points at the container that actually holds the model.
    """
    info = require_model(model_id)
    payload = ForecastRequest(
        context=context,
        prediction_length=prediction_length,
        num_samples=num_samples,
        model_id=model_id,
    )
    base = settings.FORECAST_URL or info.base_url
    raw = await _client(base, settings.FORECAST_API_KEY).post(
        info.forecast_path,
        json=payload.model_dump(),
        request_id=request_id,
    )
    return ForecastEnvelope.model_validate(raw).model_dump()


async def execute_trade(
    strategy_type: str,
    forecast_price: float,
    current_price: float,
    current_position: float,
    available_cash: float,
    initial_capital: float,
    params: dict[str, Any] | None = None,
    request_id: str | None = None,
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
    return await _client(settings.TRADING_URL, settings.TRADING_API_KEY).post(
        "/trading/execute", json=body, request_id=request_id
    )


async def compute_metrics(
    returns: list[float],
    metric: str = "performance",
    request_id: str | None = None,
) -> dict:
    return await _client(settings.METRICS_URL, settings.METRICS_API_KEY).post(
        "/metrics/v1/compute",
        json={"returns": returns, "metric": metric},
        request_id=request_id,
    )
