"""
Legacy API Data Contracts

Pydantic models defining the data contracts between AleutianLocal
and Sapheneia's legacy /v1/timeseries/forecast endpoint, plus
model-specific contracts for Chronos and TimesFM.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# ===== AleutianLocal Legacy API Contract =====

class AleutianForecastRequest(BaseModel):
    """
    Request from AleutianLocal to legacy /v1/timeseries/forecast endpoint.

    This matches the contract expected by AleutianLocal's orchestrator.
    """
    name: str = Field(
        ...,
        description="Ticker symbol (e.g., 'SPY', 'AAPL', 'BTCUSDT')"
    )
    context_period_size: int = Field(
        ...,
        description="Number of historical data points to use as context",
        gt=0
    )
    forecast_period_size: int = Field(
        ...,
        description="Number of future periods to forecast (horizon)",
        gt=0
    )
    model: str = Field(
        ...,
        description="Model identifier (e.g., 'amazon/chronos-t5-tiny', 'google/timesfm-2.0-500m-pytorch')"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "SPY",
                "context_period_size": 90,
                "forecast_period_size": 30,
                "model": "amazon/chronos-t5-tiny"
            }
        }


class AleutianForecastResponse(BaseModel):
    """
    Response to AleutianLocal from legacy endpoint.

    Simple contract: ticker name, forecast array, and status message.
    """
    name: str = Field(..., description="Ticker symbol (echoed from request)")
    forecast: List[float] = Field(..., description="Array of predicted prices")
    message: str = Field(default="Success", description="Status message")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "SPY",
                "forecast": [450.2, 451.5, 452.8, 453.1],
                "message": "Success"
            }
        }


# ===== Chronos Model Contracts =====

class ChronosInferenceRequest(BaseModel):
    """
    Chronos model inference request.

    Chronos expects historical values as context and generates
    probabilistic forecasts.
    """
    context: List[float] = Field(
        ...,
        description="Historical time series values"
    )
    prediction_length: int = Field(
        ...,
        description="Number of time steps to forecast",
        gt=0
    )
    num_samples: int = Field(
        default=20,
        description="Number of sample trajectories to generate",
        gt=0
    )
    temperature: float = Field(
        default=1.0,
        description="Sampling temperature",
        gt=0
    )
    top_k: int = Field(
        default=50,
        description="Top-k sampling parameter",
        gt=0
    )
    top_p: float = Field(
        default=1.0,
        description="Top-p (nucleus) sampling parameter",
        gt=0,
        le=1.0
    )


class ChronosInferenceResponse(BaseModel):
    """
    Chronos model inference response.

    Includes median, mean, quantiles, and sample trajectories.
    """
    median: List[float] = Field(..., description="Median forecast")
    mean: List[float] = Field(..., description="Mean forecast")
    quantiles: Dict[str, List[float]] = Field(
        default_factory=dict,
        description="Quantile forecasts (e.g., '10', '50', '90')"
    )
    samples: List[List[float]] = Field(
        default_factory=list,
        description="Sample trajectories"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Inference metadata"
    )


# ===== TimesFM Model Contracts =====

class TimesFMInferenceRequest(BaseModel):
    """
    TimesFM model inference request (internal service call).

    TimesFM's service layer accepts raw arrays in batch format.
    """
    target_inputs: List[List[float]] = Field(
        ...,
        description="Time series data in batch format [[series1], [series2], ...]"
    )
    covariates: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional covariates dictionary"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Inference parameters (context_len, horizon_len, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_inputs": [[450.0, 451.0, 452.0, 453.0]],
                "covariates": None,
                "parameters": {
                    "context_len": 64,
                    "horizon_len": 24,
                    "use_covariates": False
                }
            }
        }


class TimesFMInferenceResponse(BaseModel):
    """
    TimesFM model inference response (from service layer).

    Returns point forecasts and optionally quantile forecasts.
    """
    point_forecast: List[List[float]] = Field(
        ...,
        description="Point forecast in batch format"
    )
    quantile_forecast: Optional[List[List[List[float]]]] = Field(
        default=None,
        description="Quantile forecasts (if enabled)"
    )
    method: str = Field(
        ...,
        description="Forecasting method used ('basic' or 'covariates_enhanced')"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Inference metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "point_forecast": [[455.0, 456.0, 457.0, 458.0, 459.0]],
                "quantile_forecast": None,
                "method": "basic",
                "metadata": {
                    "input_series_count": 1,
                    "forecast_length": 5,
                    "context_length": 64
                }
            }
        }
