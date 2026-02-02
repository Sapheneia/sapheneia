"""
Shared test fixtures for orchestration tests.
"""

import pytest
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch

from orchestration.schema import (
    InferenceRequest,
    InferenceResponse,
    ContextData,
    HorizonSpec,
    ForecastData,
    ContextSummary,
    InferenceMetadata,
    Period,
    DataSource,
    DataField,
    LegacyForecastRequest,
    LegacyForecastResponse,
    ModelParams,
)


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_context_values() -> List[float]:
    """Sample price context data."""
    return [450.0, 451.2, 449.8, 452.1, 453.5, 451.0, 452.5, 450.8, 453.0, 454.2]


@pytest.fixture
def sample_forecast_values() -> List[float]:
    """Sample forecast values."""
    return [455.0, 456.2, 454.8, 457.1, 458.5]


@pytest.fixture
def sample_context_data(sample_context_values) -> ContextData:
    """Sample ContextData object."""
    return ContextData(
        values=sample_context_values,
        period=Period.DAY_1,
        source=DataSource.YAHOO,
        start_date="2025-09-01",
        end_date="2025-12-30",
        field=DataField.CLOSE,
    )


@pytest.fixture
def sample_horizon_spec() -> HorizonSpec:
    """Sample HorizonSpec object."""
    return HorizonSpec(
        length=10,
        period=Period.DAY_1,
    )


@pytest.fixture
def sample_inference_request(
    sample_context_data,
    sample_horizon_spec,
) -> InferenceRequest:
    """Sample complete InferenceRequest."""
    return InferenceRequest(
        request_id="test-request-001",
        ticker="SPY",
        model="amazon/chronos-t5-tiny",
        context=sample_context_data,
        horizon=sample_horizon_spec,
    )


@pytest.fixture
def sample_inference_response(sample_forecast_values) -> InferenceResponse:
    """Sample complete InferenceResponse."""
    return InferenceResponse(
        request_id="test-request-001",
        response_id="test-response-001",
        ticker="SPY",
        model="amazon/chronos-t5-tiny",
        forecast=ForecastData(
            values=sample_forecast_values,
            period=Period.DAY_1,
            start_date="2025-12-31",
            end_date="2026-01-06",
        ),
        context_summary=ContextSummary(
            length=10,
            period=Period.DAY_1,
            source=DataSource.YAHOO,
            start_date="2025-09-01",
            end_date="2025-12-30",
            field=DataField.CLOSE,
        ),
        metadata=InferenceMetadata(
            inference_time_ms=245,
            model_version="1.0.0",
            device="cpu",
            model_family="chronos",
        ),
    )


@pytest.fixture
def sample_legacy_request(sample_context_values) -> LegacyForecastRequest:
    """Sample legacy format request."""
    return LegacyForecastRequest(
        name="SPY",
        context_period_size=90,
        forecast_period_size=10,
        model="amazon/chronos-t5-tiny",
        recent_data=sample_context_values,
        as_of_date="2025-12-30",
    )


# =============================================================================
# MOCK FIXTURES
# =============================================================================

@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for testing HTTP calls."""
    with patch("httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = client_instance
        mock.return_value.__aexit__.return_value = None
        yield client_instance


@pytest.fixture
def mock_chronos_response() -> Dict[str, Any]:
    """Mock response from Chronos service."""
    return {
        "prediction": {
            "median": [455.0, 456.2, 454.8, 457.1, 458.5],
            "mean": [455.0, 456.2, 454.8, 457.1, 458.5],
            "quantiles": {
                "10": [453.0, 454.0, 452.5, 455.0, 456.0],
                "90": [457.0, 458.5, 457.0, 459.5, 461.0],
            },
            "device": "cpu",
        }
    }


@pytest.fixture
def mock_timesfm_response() -> Dict[str, Any]:
    """Mock response from TimesFM service."""
    return {
        "point_forecast": [[455.0, 456.2, 454.8, 457.1, 458.5]],
        "metadata": {
            "device": "cuda:0",
        },
    }
