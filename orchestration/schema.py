"""
Inference Data Contracts

Pydantic models defining the standardized request/response contracts
for the unified inference API. All requests include full metadata for
traceability, audit, and data provenance.

Design Principles:
- Every request has a unique ID for tracing
- All timestamps are ISO8601 UTC
- Data provenance tracked via source and period
- Responses reference their originating request
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime, date, timezone
import uuid


# =============================================================================
# ENUMS
# =============================================================================

class Period(str, Enum):
    """
    Time period/frequency of the data.

    Used to specify the granularity of both input context
    and output forecasts.
    """
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class DataSource(str, Enum):
    """
    Origin of the financial data.

    Tracks where the data was originally fetched from,
    important for data quality and licensing compliance.
    """
    YAHOO = "yahoo"
    ALPACA = "alpaca"
    BINANCE = "binance"
    POLYGON = "polygon"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    INFLUXDB = "influxdb"      # Internal cache/storage
    SYNTHETIC = "synthetic"    # Generated test data
    UNKNOWN = "unknown"


class DataField(str, Enum):
    """
    Which OHLCV field the values represent.
    """
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    ADJ_CLOSE = "adj_close"
    VOLUME = "volume"


# =============================================================================
# CONTEXT DATA (Input)
# =============================================================================

class ContextData(BaseModel):
    """
    Historical time-series data provided as context for forecasting.

    This is the input data that the model uses to generate predictions.
    Includes full provenance metadata.

    Attributes:
        values: The actual time-series values (oldest first)
        period: Frequency of the data points
        source: Where the data originated
        start_date: First date in the series (ISO format)
        end_date: Last date in the series (ISO format)
        field: Which OHLCV field these values represent
    """
    values: List[float] = Field(
        ...,
        min_length=1,
        description="Time-series values, oldest first"
    )
    period: Period = Field(
        ...,
        description="Data frequency (1m, 1h, 1d, etc.)"
    )
    source: DataSource = Field(
        ...,
        description="Data origin (yahoo, alpaca, binance, etc.)"
    )
    start_date: str = Field(
        ...,
        description="First date in series (ISO format YYYY-MM-DD)"
    )
    end_date: str = Field(
        ...,
        description="Last date in series (ISO format YYYY-MM-DD)"
    )
    field: DataField = Field(
        default=DataField.CLOSE,
        description="OHLCV field (close, open, high, low, volume)"
    )

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate ISO date format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: {v}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "values": [450.0, 451.2, 449.8, 452.1, 453.5],
                "period": "1d",
                "source": "yahoo",
                "start_date": "2025-09-01",
                "end_date": "2025-12-30",
                "field": "close"
            }
        }


# =============================================================================
# HORIZON SPEC
# =============================================================================

class HorizonSpec(BaseModel):
    """
    Specification for the forecast horizon.

    Attributes:
        length: Number of periods to forecast
        period: Frequency of forecast points (should match context period)
    """
    length: int = Field(
        ...,
        gt=0,
        le=365,
        description="Number of periods to forecast"
    )
    period: Period = Field(
        ...,
        description="Forecast frequency (should match context period)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "length": 10,
                "period": "1d"
            }
        }


# =============================================================================
# INFERENCE REQUEST
# =============================================================================

class ModelParams(BaseModel):
    """
    Model-specific inference parameters.

    Different models support different parameters.
    This provides a typed interface for common ones.
    """
    num_samples: int = Field(
        default=20,
        gt=0,
        le=100,
        description="Number of sample trajectories for probabilistic models"
    )
    temperature: float = Field(
        default=1.0,
        gt=0,
        le=2.0,
        description="Sampling temperature"
    )
    top_k: int = Field(
        default=50,
        gt=0,
        description="Top-k sampling parameter"
    )
    top_p: float = Field(
        default=1.0,
        gt=0,
        le=1.0,
        description="Nucleus sampling parameter"
    )
    quantiles: Optional[List[float]] = Field(
        default=None,
        description="Quantile levels to compute (e.g., [0.1, 0.5, 0.9])"
    )


class InferenceRequest(BaseModel):
    """
    Unified inference request for all forecasting models.

    This is the primary contract between Aleutian (Go orchestrator)
    and Sapheneia (Python inference engine).

    Key Design Decisions:
    - request_id: UUID for full request tracing
    - timestamp: When the request was created (not when data ends)
    - context: Full data with provenance metadata
    - horizon: What to forecast
    - model: Which model to use
    - params: Model-specific parameters

    Example:
        POST /inference/v1/predict
        {
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-12-31T14:30:00Z",
            "ticker": "SPY",
            "model": "amazon/chronos-t5-tiny",
            "context": {...},
            "horizon": {...}
        }
    """
    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique request identifier for tracing"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Request creation timestamp (UTC)"
    )

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Ticker symbol (e.g., SPY, BTCUSDT)"
    )
    model: str = Field(
        ...,
        description="Model identifier (e.g., amazon/chronos-t5-tiny)"
    )

    context: ContextData = Field(
        ...,
        description="Historical data for model context"
    )
    horizon: HorizonSpec = Field(
        ...,
        description="Forecast horizon specification"
    )

    params: Optional[ModelParams] = Field(
        default=None,
        description="Model-specific inference parameters"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-12-31T14:30:00Z",
                "ticker": "SPY",
                "model": "amazon/chronos-t5-tiny",
                "context": {
                    "values": [450.0, 451.2, 449.8, 452.1, 453.5],
                    "period": "1d",
                    "source": "yahoo",
                    "start_date": "2025-09-01",
                    "end_date": "2025-12-30",
                    "field": "close"
                },
                "horizon": {
                    "length": 10,
                    "period": "1d"
                },
                "params": {
                    "num_samples": 20,
                    "temperature": 1.0
                }
            }
        }


# =============================================================================
# INFERENCE RESPONSE
# =============================================================================

class ForecastData(BaseModel):
    """
    Forecast output from the model.

    Attributes:
        values: Predicted values for each horizon step
        period: Frequency of forecast points
        start_date: First forecast date
        end_date: Last forecast date
    """
    values: List[float] = Field(
        ...,
        min_length=1,
        description="Forecast values"
    )
    period: Period = Field(
        ...,
        description="Forecast frequency"
    )
    start_date: str = Field(
        ...,
        description="First forecast date (ISO format)"
    )
    end_date: str = Field(
        ...,
        description="Last forecast date (ISO format)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "values": [452.1, 453.0, 451.8, 454.2, 455.0],
                "period": "1d",
                "start_date": "2025-12-31",
                "end_date": "2026-01-06"
            }
        }


class ContextSummary(BaseModel):
    """
    Summary of the context data used for inference.

    Echoed back in response for verification and audit.
    """
    length: int = Field(..., description="Number of context points used")
    period: Period = Field(..., description="Context data frequency")
    source: DataSource = Field(..., description="Data origin")
    start_date: str = Field(..., description="Context start date")
    end_date: str = Field(..., description="Context end date")
    field: DataField = Field(..., description="OHLCV field used")


class InferenceMetadata(BaseModel):
    """
    Metadata about the inference execution.
    """
    inference_time_ms: int = Field(
        ...,
        description="Inference execution time in milliseconds"
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Model version or checkpoint"
    )
    device: Optional[str] = Field(
        default=None,
        description="Compute device used (cpu, cuda:0, etc.)"
    )
    model_family: Optional[str] = Field(
        default=None,
        description="Model family (chronos, timesfm, moirai, etc.)"
    )


class QuantileForecast(BaseModel):
    """
    Quantile forecasts for probabilistic models.
    """
    quantile: float = Field(..., description="Quantile level (e.g., 0.1, 0.5, 0.9)")
    values: List[float] = Field(..., description="Forecast values at this quantile")


class InferenceResponse(BaseModel):
    """
    Unified inference response from all forecasting models.

    Links back to the originating request via request_id.
    Provides both point forecasts and optional quantile forecasts.

    Key Design Decisions:
    - request_id: Links to originating request
    - response_id: Unique ID for this response
    - context_summary: Echoes what context was used
    - forecast: Point forecast output
    - quantiles: Optional probabilistic forecasts
    """
    request_id: str = Field(
        ...,
        description="Originating request ID"
    )
    response_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique response identifier"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Response creation timestamp (UTC)"
    )

    ticker: str = Field(..., description="Ticker symbol")
    model: str = Field(..., description="Model used")

    forecast: ForecastData = Field(
        ...,
        description="Point forecast output"
    )

    context_summary: ContextSummary = Field(
        ...,
        description="Summary of context data used"
    )

    quantiles: Optional[List[QuantileForecast]] = Field(
        default=None,
        description="Optional quantile forecasts"
    )

    metadata: InferenceMetadata = Field(
        ...,
        description="Inference execution metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "response_id": "660f9511-f30c-52e5-b827-557766551111",
                "timestamp": "2025-12-31T14:30:02Z",
                "ticker": "SPY",
                "model": "amazon/chronos-t5-tiny",
                "forecast": {
                    "values": [452.1, 453.0, 451.8, 454.2, 455.0],
                    "period": "1d",
                    "start_date": "2025-12-31",
                    "end_date": "2026-01-06"
                },
                "context_summary": {
                    "length": 90,
                    "period": "1d",
                    "source": "yahoo",
                    "start_date": "2025-09-01",
                    "end_date": "2025-12-30",
                    "field": "close"
                },
                "quantiles": [
                    {"quantile": 0.1, "values": [450.0, 451.0, 449.5, 452.0, 453.0]},
                    {"quantile": 0.9, "values": [454.0, 455.0, 454.0, 456.5, 457.0]}
                ],
                "metadata": {
                    "inference_time_ms": 245,
                    "model_version": "1.0.0",
                    "device": "cuda:0",
                    "model_family": "chronos"
                }
            }
        }


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

class LegacyForecastRequest(BaseModel):
    """
    DEPRECATED: Legacy request format for backwards compatibility.

    This matches the old AleutianForecastRequest contract.
    New integrations should use InferenceRequest.
    """
    name: str = Field(..., description="Ticker symbol")
    context_period_size: int = Field(..., gt=0)
    forecast_period_size: int = Field(..., gt=0)
    model: str = Field(...)
    recent_data: List[float] = Field(..., min_length=1)
    as_of_date: Optional[str] = Field(default=None)


class LegacyForecastResponse(BaseModel):
    """
    DEPRECATED: Legacy response format for backwards compatibility.

    This matches the old AleutianForecastResponse contract.
    New integrations should use InferenceResponse.
    """
    name: str
    forecast: List[float]
    message: str = "Success"
