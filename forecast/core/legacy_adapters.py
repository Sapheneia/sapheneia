"""
Legacy API Adapters

Pure transformation functions for converting between AleutianLocal's
legacy API format and model-specific inference formats.

All functions are pure (no side effects) and type-safe using Pydantic.
"""

from typing import List, Dict, Any, Optional
from .legacy_schema import (
    AleutianForecastRequest,
    AleutianForecastResponse,
    ChronosInferenceRequest,
    ChronosInferenceResponse,
    TimesFMInferenceRequest,
    TimesFMInferenceResponse,
)


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

    raise ValueError(f"Unknown model family: {model_name}")


def get_model_base_path(model_family: str) -> str:
    """
    Get API base path for model family.

    Pure function: Maps model family to its REST API base path.

    Args:
        model_family: Model family name (e.g., "chronos", "timesfm")

    Returns:
        Base path (e.g., "/forecast/v1/chronos")

    Raises:
        ValueError: If model family has no registered base path

    Examples:
        >>> get_model_base_path("chronos")
        "/forecast/v1/chronos"
        >>> get_model_base_path("timesfm")
        "/forecast/v1/timesfm20"
    """
    paths = {
        "chronos": "/forecast/v1/chronos",
        "timesfm": "/forecast/v1/timesfm20",
        "moirai": "/forecast/v1/moirai",
        "granite": "/forecast/v1/granite",
        "moment": "/forecast/v1/moment",
    }

    if model_family not in paths:
        raise ValueError(f"No base path for model family: {model_family}")

    return paths[model_family]


def aleutian_to_chronos(
    request: AleutianForecastRequest,
    historical_prices: List[float]
) -> ChronosInferenceRequest:
    """
    Transform AleutianLocal request to Chronos format.

    Pure function: Converts legacy API contract to Chronos inference format.

    Args:
        request: AleutianLocal forecast request (from timeseries.go)
        historical_prices: Array of historical close prices from InfluxDB

    Returns:
        Chronos inference request ready for /forecast/v1/chronos/inference

    Examples:
        >>> req = AleutianForecastRequest(
        ...     name="SPY",
        ...     context_period_size=90,
        ...     forecast_period_size=10,
        ...     model="amazon/chronos-t5-tiny"
        ... )
        >>> prices = [145.2, 146.1, 145.8, ...]
        >>> chronos_req = aleutian_to_chronos(req, prices)
        >>> chronos_req.context == prices
        True
        >>> chronos_req.prediction_length == 10
        True
    """
    return ChronosInferenceRequest(
        context=historical_prices,
        prediction_length=request.forecast_period_size,
        num_samples=20,  # Default sampling for probabilistic forecast
        temperature=1.0,
        top_k=50,
        top_p=1.0
    )


def chronos_to_aleutian(
    chronos_response: ChronosInferenceResponse,
    ticker: str
) -> AleutianForecastResponse:
    """
    Transform Chronos response to AleutianLocal format.

    Pure function: Converts Chronos inference result to legacy API contract.

    Args:
        chronos_response: Chronos inference result (with median, mean, quantiles)
        ticker: Ticker symbol (e.g., "SPY")

    Returns:
        AleutianLocal forecast response matching datatypes/evaluator.go contract

    Examples:
        >>> chronos_resp = ChronosInferenceResponse(
        ...     median=[450.2, 451.5, 452.8],
        ...     mean=[450.1, 451.4, 452.9],
        ...     quantiles={},
        ...     samples=[],
        ...     metadata={}
        ... )
        >>> aleutian_resp = chronos_to_aleutian(chronos_resp, "SPY")
        >>> aleutian_resp.name == "SPY"
        True
        >>> aleutian_resp.forecast == [450.2, 451.5, 452.8]
        True
    """
    return AleutianForecastResponse(
        name=ticker,
        forecast=chronos_response.median,  # Use median as point forecast
        message="Success"
    )


def aleutian_to_timesfm(
    request: AleutianForecastRequest,
    historical_prices: List[float]
) -> TimesFMInferenceRequest:
    """
    Transform AleutianLocal request to TimesFM format.

    Pure function: Converts legacy API contract to TimesFM service format.

    Args:
        request: AleutianLocal forecast request (from timeseries.go)
        historical_prices: Array of historical close prices from InfluxDB

    Returns:
        TimesFM inference request ready for service layer call

    Note:
        TimesFM expects data in batch format (list of lists), so we wrap
        the single series in a list.

    Examples:
        >>> req = AleutianForecastRequest(
        ...     name="SPY",
        ...     context_period_size=252,
        ...     forecast_period_size=10,
        ...     model="google/timesfm-2.0-500m-pytorch"
        ... )
        >>> prices = [450.0, 451.0, 452.0, ...]
        >>> timesfm_req = aleutian_to_timesfm(req, prices)
        >>> timesfm_req.target_inputs == [[450.0, 451.0, 452.0, ...]]
        True
        >>> timesfm_req.parameters["horizon_len"] == 10
        True
    """
    return TimesFMInferenceRequest(
        target_inputs=[historical_prices],  # Wrap in list for batch format
        covariates=None,  # No covariates from AleutianLocal
        parameters={
            "context_len": request.context_period_size,
            "horizon_len": request.forecast_period_size,
            "use_covariates": False,
            "use_quantiles": False  # Disable quantiles for faster inference
        }
    )


def timesfm_to_aleutian(
    timesfm_response: TimesFMInferenceResponse,
    ticker: str
) -> AleutianForecastResponse:
    """
    Transform TimesFM response to AleutianLocal format.

    Pure function: Converts TimesFM service result to legacy API contract.

    Args:
        timesfm_response: TimesFM service result (with point_forecast in batch format)
        ticker: Ticker symbol (e.g., "SPY")

    Returns:
        AleutianLocal forecast response matching datatypes/evaluator.go contract

    Note:
        TimesFM returns forecasts in batch format [[forecast1], [forecast2], ...].
        We extract the first (and only) forecast series.

    Examples:
        >>> timesfm_resp = TimesFMInferenceResponse(
        ...     point_forecast=[[455.0, 456.0, 457.0]],
        ...     quantile_forecast=None,
        ...     method="basic",
        ...     metadata={}
        ... )
        >>> aleutian_resp = timesfm_to_aleutian(timesfm_resp, "SPY")
        >>> aleutian_resp.name == "SPY"
        True
        >>> aleutian_resp.forecast == [455.0, 456.0, 457.0]
        True
    """
    return AleutianForecastResponse(
        name=ticker,
        forecast=timesfm_response.point_forecast[0],  # Extract first series from batch
        message="Success"
    )


# Future: Add adapters for other models
# def aleutian_to_moirai(...) -> MoiraiInferenceRequest
# def moirai_to_aleutian(...) -> AleutianForecastResponse
