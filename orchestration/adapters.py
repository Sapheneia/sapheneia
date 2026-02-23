"""
Inference Adapters

Pure transformation functions for converting between the unified
InferenceRequest/Response format and model-specific inference formats.

All functions are pure (no side effects) and type-safe using Pydantic.

Supported Model Families:
- Chronos (Amazon): chronos-t5-*, chronos-bolt-*
- TimesFM (Google): timesfm-1.0, timesfm-2.0
- Moirai (Salesforce): moirai-1.1-*
- Granite (IBM): granite-ttm-*
- Moment (AutonLab): moment-1-*
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

from shared.errors import ComputationError
from .schema import (
    InferenceRequest,
    InferenceResponse,
    ContextData,
    ForecastData,
    ContextSummary,
    InferenceMetadata,
    HorizonSpec,
    Period,
    DataSource,
    DataField,
    LegacyForecastRequest,
    LegacyForecastResponse,
)


# =============================================================================
# MODEL FAMILY DETECTION
# =============================================================================

def determine_model_family(model_name: str) -> str:
    """
    Extract model family from model identifier.

    Pure function: Takes model name string, returns family classification.

    Args:
        model_name: Full model ID (e.g., "amazon/chronos-t5-tiny")

    Returns:
        Model family ("chronos", "timesfm", "moirai", etc.)

    Raises:
        ValueError: If model family cannot be determined

    Examples:
        >>> determine_model_family("amazon/chronos-t5-tiny")
        "chronos"
        >>> determine_model_family("google/timesfm-2.0-500m-pytorch")
        "timesfm"
    """
    lower_name = model_name.lower()

    if "chronos" in lower_name:
        return "chronos"
    if "timesfm" in lower_name:
        return "timesfm"
    if "moirai" in lower_name:
        return "moirai"
    if "granite" in lower_name:
        return "granite"
    if "moment" in lower_name:
        return "moment"
    if "lag-llama" in lower_name:
        return "lagllama"
    if "yinglong" in lower_name:
        return "yinglong"

    raise ValueError(f"Unknown model family: {model_name}")


def get_model_endpoint(model_family: str) -> str:
    """
    Get API endpoint path for model family.

    Args:
        model_family: Model family name

    Returns:
        API endpoint path (e.g., "/forecast/v1/chronos/inference")
    """
    endpoints = {
        "chronos": "/forecast/v1/chronos/inference",
        "timesfm": "/forecast/v1/timesfm20/inference",
        "moirai": "/forecast/v1/moirai/inference",
        "granite": "/forecast/v1/granite/inference",
        "moment": "/forecast/v1/moment/inference",
    }

    if model_family not in endpoints:
        raise ValueError(f"No endpoint for model family: {model_family}")

    return endpoints[model_family]


# =============================================================================
# DATE CALCULATIONS
# =============================================================================

class DateParseError(ValueError):
    """Raised when a date string cannot be parsed."""
    pass


def parse_date(date_str: str, field_name: str = "date") -> datetime:
    """
    Parse a date string, supporting multiple formats.

    Args:
        date_str: Date string to parse
        field_name: Name of the field for error messages

    Returns:
        Parsed datetime object

    Raises:
        DateParseError: If the date cannot be parsed
    """
    if not date_str:
        raise DateParseError(f"{field_name} is required but was empty")

    date_str = str(date_str).strip()

    # Try YYYY-MM-DD format
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass

    # Try YYYYMMDD format
    if len(date_str) == 8 and date_str.isdigit():
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            pass

    # Try ISO format with time component
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    raise DateParseError(
        f"Invalid {field_name} format: '{date_str}'. "
        f"Expected YYYY-MM-DD or YYYYMMDD format."
    )


def calculate_forecast_dates(
    context_end_date: str,
    horizon_length: int,
    period: Period
) -> Tuple[str, str]:
    """
    Calculate forecast start and end dates based on context end date and horizon.

    Args:
        context_end_date: Last date of context data (YYYY-MM-DD or YYYYMMDD)
        horizon_length: Number of periods to forecast
        period: Forecast period frequency

    Returns:
        Tuple of (forecast_start_date, forecast_end_date) in YYYY-MM-DD format

    Raises:
        DateParseError: If context_end_date cannot be parsed
    """
    base_date = parse_date(context_end_date, "context_end_date")

    # Calculate delta based on period
    if period == Period.DAY_1:
        delta = timedelta(days=1)
    elif period == Period.WEEK_1:
        delta = timedelta(weeks=1)
    elif period == Period.HOUR_1:
        delta = timedelta(hours=1)
    elif period == Period.HOUR_4:
        delta = timedelta(hours=4)
    elif period == Period.MINUTE_1:
        delta = timedelta(minutes=1)
    elif period == Period.MINUTE_5:
        delta = timedelta(minutes=5)
    elif period == Period.MINUTE_15:
        delta = timedelta(minutes=15)
    elif period == Period.MINUTE_30:
        delta = timedelta(minutes=30)
    elif period == Period.MONTH_1:
        delta = timedelta(days=30)  # Approximation
    else:
        delta = timedelta(days=1)

    # Forecast starts the period after context ends
    forecast_start = base_date + delta
    forecast_end = base_date + (delta * horizon_length)

    return forecast_start.strftime("%Y-%m-%d"), forecast_end.strftime("%Y-%m-%d")


# =============================================================================
# CHRONOS ADAPTERS
# =============================================================================

def inference_to_chronos(request: InferenceRequest) -> Dict[str, Any]:
    """
    Transform unified InferenceRequest to Chronos inference format.

    Args:
        request: Unified inference request

    Returns:
        Chronos-compatible request dict for /forecast/v1/chronos/inference
    """
    params = request.params or {}

    return {
        "context": request.context.values,
        "prediction_length": request.horizon.length,
        "num_samples": getattr(params, 'num_samples', 20),
        "temperature": getattr(params, 'temperature', 1.0),
        "top_k": getattr(params, 'top_k', 50),
        "top_p": getattr(params, 'top_p', 1.0),
    }


def chronos_to_inference(
    chronos_response: Dict[str, Any],
    request: InferenceRequest,
    inference_time_ms: int
) -> InferenceResponse:
    """
    Transform Chronos inference response to unified InferenceResponse.

    Args:
        chronos_response: Raw response from Chronos endpoint
        request: Original inference request
        inference_time_ms: Time taken for inference

    Returns:
        Unified InferenceResponse
    """
    prediction = chronos_response.get("prediction", chronos_response)

    # Use median as point forecast
    forecast_values = prediction.get("median", prediction.get("mean", []))
    if not forecast_values:
        raise ComputationError(
            message="Chronos response missing forecast values (no 'median' or 'mean' key)",
            details={"model_family": "chronos", "available_keys": list(prediction.keys())},
        )

    # Calculate forecast dates
    start_date, end_date = calculate_forecast_dates(
        request.context.end_date,
        request.horizon.length,
        request.horizon.period
    )

    # Build quantile forecasts if available
    quantiles = None
    if "quantiles" in prediction and prediction["quantiles"]:
        from .schema import QuantileForecast
        quantiles = [
            QuantileForecast(quantile=float(q) / 100, values=vals)
            for q, vals in prediction["quantiles"].items()
        ]

    return InferenceResponse(
        request_id=request.request_id,
        ticker=request.ticker,
        model=request.model,
        forecast=ForecastData(
            values=forecast_values,
            period=request.horizon.period,
            start_date=start_date,
            end_date=end_date,
        ),
        context_summary=ContextSummary(
            length=len(request.context.values),
            period=request.context.period,
            source=request.context.source,
            start_date=request.context.start_date,
            end_date=request.context.end_date,
            field=request.context.field,
        ),
        quantiles=quantiles,
        metadata=InferenceMetadata(
            inference_time_ms=inference_time_ms,
            model_version="1.0.0",
            device=prediction.get("device", "unknown"),
            model_family="chronos",
        ),
    )


# =============================================================================
# TIMESFM ADAPTERS
# =============================================================================

def inference_to_timesfm(request: InferenceRequest) -> Dict[str, Any]:
    """
    Transform unified InferenceRequest to TimesFM inference format.

    TimesFM expects data in batch format (list of lists).

    Args:
        request: Unified inference request

    Returns:
        TimesFM-compatible request dict
    """
    return {
        "target_inputs": [request.context.values],  # Batch format
        "covariates": None,
        "parameters": {
            "context_len": len(request.context.values),
            "horizon_len": request.horizon.length,
            "use_covariates": False,
            "use_quantiles": False,
        }
    }


def timesfm_to_inference(
    timesfm_response: Dict[str, Any],
    request: InferenceRequest,
    inference_time_ms: int
) -> InferenceResponse:
    """
    Transform TimesFM inference response to unified InferenceResponse.

    TimesFM returns forecasts in batch format [[forecast1], [forecast2], ...].

    Args:
        timesfm_response: Raw response from TimesFM service
        request: Original inference request
        inference_time_ms: Time taken for inference

    Returns:
        Unified InferenceResponse
    """
    # Extract first series from batch format
    try:
        point_forecast = timesfm_response["point_forecast"][0]
    except KeyError:
        raise ComputationError(
            message="TimesFM response missing 'point_forecast' key",
            details={"model_family": "timesfm", "available_keys": list(timesfm_response.keys())},
        )
    except IndexError:
        raise ComputationError(
            message="TimesFM 'point_forecast' is empty",
            details={"model_family": "timesfm"},
        )
    if not point_forecast:
        raise ComputationError(
            message="TimesFM returned empty forecast values",
            details={"model_family": "timesfm"},
        )

    # Calculate forecast dates
    start_date, end_date = calculate_forecast_dates(
        request.context.end_date,
        request.horizon.length,
        request.horizon.period
    )

    return InferenceResponse(
        request_id=request.request_id,
        ticker=request.ticker,
        model=request.model,
        forecast=ForecastData(
            values=point_forecast,
            period=request.horizon.period,
            start_date=start_date,
            end_date=end_date,
        ),
        context_summary=ContextSummary(
            length=len(request.context.values),
            period=request.context.period,
            source=request.context.source,
            start_date=request.context.start_date,
            end_date=request.context.end_date,
            field=request.context.field,
        ),
        metadata=InferenceMetadata(
            inference_time_ms=inference_time_ms,
            model_version="2.0",
            device=timesfm_response.get("metadata", {}).get("device", "unknown"),
            model_family="timesfm",
        ),
    )


# =============================================================================
# LEGACY ADAPTERS (Backwards Compatibility)
# =============================================================================

def legacy_to_inference(
    legacy_request: LegacyForecastRequest,
    source: DataSource = DataSource.INFLUXDB,
    period: Period = Period.DAY_1,
) -> InferenceRequest:
    """
    Convert legacy AleutianForecastRequest to new InferenceRequest.

    Used for backwards compatibility during migration.

    Args:
        legacy_request: Old-format request from Aleutian
        source: Data source (defaults to influxdb since Aleutian fetches)
        period: Data period (defaults to daily)

    Returns:
        New-format InferenceRequest
    """
    # Calculate approximate dates from data length
    # This is imprecise but maintains compatibility
    import logging
    from datetime import date as date_type
    logger = logging.getLogger(__name__)

    end_date = date_type.today()
    if legacy_request.as_of_date:
        try:
            parsed = parse_date(legacy_request.as_of_date, "as_of_date")
            end_date = parsed.date()
        except DateParseError as e:
            logger.warning(
                f"Invalid as_of_date in legacy request: {legacy_request.as_of_date}. "
                f"Using today's date. Error: {e}"
            )

    # Estimate start date based on data length
    data_length = len(legacy_request.recent_data)
    start_date = end_date - timedelta(days=data_length)

    return InferenceRequest(
        ticker=legacy_request.name,
        model=legacy_request.model,
        context=ContextData(
            values=legacy_request.recent_data,
            period=period,
            source=source,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            field=DataField.CLOSE,
        ),
        horizon=HorizonSpec(
            length=legacy_request.forecast_period_size,
            period=period,
        ),
    )


def inference_to_legacy(response: InferenceResponse) -> LegacyForecastResponse:
    """
    Convert new InferenceResponse to legacy AleutianForecastResponse.

    Used for backwards compatibility during migration.

    Args:
        response: New-format response

    Returns:
        Old-format response for Aleutian compatibility
    """
    return LegacyForecastResponse(
        name=response.ticker,
        forecast=response.forecast.values,
        message="Success",
    )
