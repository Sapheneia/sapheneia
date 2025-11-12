"""
Pytest configuration and shared fixtures for Trading Strategies tests.

Provides common test fixtures and utilities for all test modules.
"""

import pytest
import numpy as np
import os
from fastapi.testclient import TestClient
from unittest.mock import patch

# Import the FastAPI app
from trading.main import app

# Import settings (will be mocked in tests)
from trading.core.config import settings

# Note: Rate limiting is enabled for tests to verify it works correctly
# Some tests may hit rate limits (429) which is expected behavior
# Tests that specifically need to avoid rate limits should handle this separately


@pytest.fixture
def test_client():
    """
    FastAPI test client for testing API endpoints.

    Returns:
        TestClient instance for the trading app
    """
    # Note: Rate limiting uses memory storage which resets between test runs
    # Individual tests shouldn't hit rate limits (10/minute for execute endpoint)
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """
    Authentication headers for testing API endpoints.

    Returns:
        Dictionary with Authorization header using test API key
    """
    # Use the actual API key from settings for testing
    return {"Authorization": f"Bearer {settings.TRADING_API_KEY}"}


@pytest.fixture
def sample_ohlc_data():
    """
    Generate sample OHLC data for testing.

    Returns:
        Dictionary with open_history, high_history, low_history, close_history
    """
    np.random.seed(42)  # For reproducible tests
    n_periods = 30

    base_price = 100.0
    open_history = np.random.uniform(95, 105, n_periods).tolist()
    high_history = np.random.uniform(100, 110, n_periods).tolist()
    low_history = np.random.uniform(90, 100, n_periods).tolist()
    close_history = np.random.uniform(95, 105, n_periods).tolist()

    return {
        "open_history": open_history,
        "high_history": high_history,
        "low_history": low_history,
        "close_history": close_history,
    }


@pytest.fixture
def base_params():
    """
    Base parameters for strategy testing.

    Returns:
        Dictionary with common strategy parameters
    """
    return {
        "forecast_price": 105.0,
        "current_price": 100.0,
        "current_position": 0.0,
        "available_cash": 100000.0,
        "initial_capital": 100000.0,
    }


@pytest.fixture
def sample_threshold_params(base_params, sample_ohlc_data):
    """
    Sample parameters for threshold strategy testing.

    Args:
        base_params: Base parameters fixture
        sample_ohlc_data: OHLC data fixture

    Returns:
        Dictionary with threshold strategy parameters
    """
    params = base_params.copy()
    params.update(
        {
            "strategy_type": "threshold",
            "threshold_type": "absolute",
            "threshold_value": 0.0,
            "execution_size": 100.0,
        }
    )
    params.update(sample_ohlc_data)
    return params


@pytest.fixture
def sample_return_params(base_params, sample_ohlc_data):
    """
    Sample parameters for return strategy testing.

    Args:
        base_params: Base parameters fixture
        sample_ohlc_data: OHLC data fixture

    Returns:
        Dictionary with return strategy parameters
    """
    params = base_params.copy()
    params.update(
        {
            "strategy_type": "return",
            "position_sizing": "fixed",
            "threshold_value": 0.05,  # 5%
            "execution_size": 10.0,
        }
    )
    params.update(sample_ohlc_data)
    return params


@pytest.fixture
def sample_quantile_params(base_params, sample_ohlc_data):
    """
    Sample parameters for quantile strategy testing.

    Args:
        base_params: Base parameters fixture
        sample_ohlc_data: OHLC data fixture

    Returns:
        Dictionary with quantile strategy parameters
    """
    params = base_params.copy()
    params.update(
        {
            "strategy_type": "quantile",
            "which_history": "close",
            "window_history": 20,
            "quantile_signals": {
                1: {"range": [0, 5], "signal": "sell", "multiplier": 1.0},
                2: {"range": [90, 95], "signal": "buy", "multiplier": 0.75},
                3: {"range": [95, 100], "signal": "buy", "multiplier": 1.0},
            },
            "position_sizing": "fixed",
            "execution_size": 100.0,
        }
    )
    params.update(sample_ohlc_data)
    return params


@pytest.fixture(scope="session")
def test_env():
    """
    Set up test environment variables.

    Yields:
        Dictionary of test environment variables
    """
    old_env = {}
    test_env_vars = {
        "TRADING_API_KEY": "test_trading_api_key_for_testing_only_32_chars_min",
        "ENVIRONMENT": "test",
        "LOG_LEVEL": "DEBUG",
        "TRADING_API_PORT": "9000",
        "TRADING_API_HOST": "0.0.0.0",
    }

    # Save old values
    for key, value in test_env_vars.items():
        old_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield test_env_vars

    # Restore old values
    for key, value in old_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
