"""
Pytest configuration and fixtures for Sapheneia tests.
"""

import pytest
import sys
from pathlib import Path

# Add forecast package to Python path
forecast_path = Path(__file__).parent.parent / "forecast"
sys.path.insert(0, str(forecast_path))


@pytest.fixture
def sample_aleutian_request():
    """Fixture providing a sample AleutianForecastRequest."""
    from forecast.core.legacy_schema import AleutianForecastRequest
    
    return AleutianForecastRequest(
        name="SPY",
        context_period_size=90,
        forecast_period_size=10,
        model="amazon/chronos-t5-tiny"
    )


@pytest.fixture
def sample_historical_prices():
    """Fixture providing sample historical price data."""
    return [450.0 + i * 0.1 for i in range(90)]


@pytest.fixture
def sample_chronos_response():
    """Fixture providing a sample ChronosInferenceResponse."""
    from forecast.core.legacy_schema import ChronosInferenceResponse
    
    return ChronosInferenceResponse(
        median=[455.0, 456.0, 457.0, 458.0, 459.0, 460.0, 461.0, 462.0, 463.0, 464.0],
        mean=[454.9, 455.9, 456.9, 457.9, 458.9, 459.9, 460.9, 461.9, 462.9, 463.9],
        quantiles={
            "10": [453.0] * 10,
            "50": [455.0, 456.0, 457.0, 458.0, 459.0, 460.0, 461.0, 462.0, 463.0, 464.0],
            "90": [457.0] * 10,
        },
        samples=[
            [455.0 + i * 0.2 for i in range(10)],
            [454.0 + i * 0.2 for i in range(10)],
            [456.0 + i * 0.2 for i in range(10)],
        ],
        metadata={
            "context_length": 90,
            "prediction_length": 10,
            "num_samples": 20,
            "model_variant": "amazon/chronos-t5-tiny",
            "inference_time_seconds": 2.45
        }
    )


@pytest.fixture
def mock_data_service_response():
    """Fixture providing a mock data service response."""
    return {
        "ticker": "SPY",
        "data": [
            {"time": f"2023-01-{i:02d}", "close": 450.0 + i * 0.1}
            for i in range(1, 91)
        ]
    }
