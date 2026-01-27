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
def sample_historical_prices():
    """Fixture providing sample historical price data."""
    return [450.0 + i * 0.1 for i in range(90)]


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


@pytest.fixture
def sample_data_file(tmp_path):
    """Fixture providing a sample CSV data file for testing."""
    import pandas as pd

    # Create sample data
    data = {
        "date": [f"2023-01-{i:02d}" for i in range(1, 31)],
        "value": [100.0 + i * 0.5 for i in range(30)]
    }
    df = pd.DataFrame(data)

    # Create the data/uploads directory structure in tmp_path
    uploads_dir = tmp_path / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Write to file
    file_path = uploads_dir / "sample_data.csv"
    df.to_csv(file_path, index=False)

    return file_path


# Note: client and auth_headers fixtures are defined locally in test_endpoints.py
# to handle import errors gracefully when forecast.main cannot be imported
