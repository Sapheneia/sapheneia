"""
Pytest configuration and shared fixtures for Sapheneia tests.

Provides common test fixtures and utilities for all test modules.
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import os
import tempfile
import shutil

# Import the FastAPI app
from api.main import app


@pytest.fixture
def client():
    """FastAPI test client for testing API endpoints."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Authentication headers for testing API endpoints."""
    return {"Authorization": "Bearer test_secret_key"}


@pytest.fixture
def sample_data_file(tmp_path):
    """
    Create a sample CSV file for testing.
    
    Creates a temporary CSV file with 100 rows of time series data.
    """
    import pandas as pd
    
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=100, freq='D'),
        'value': range(100),
        'category': ['A'] * 50 + ['B'] * 50
    })
    
    file_path = tmp_path / "test_data.csv"
    df.to_csv(file_path, index=False)
    return file_path


@pytest.fixture
def sample_large_data_file(tmp_path):
    """
    Create a larger sample CSV file for testing (500 rows).
    
    Useful for testing performance and larger data processing.
    """
    import pandas as pd
    
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=500, freq='D'),
        'value': range(500),
        'volume': [100] * 500
    })
    
    file_path = tmp_path / "test_large_data.csv"
    df.to_csv(file_path, index=False)
    return file_path


@pytest.fixture
def temp_data_dir(tmp_path):
    """
    Create a temporary data directory structure for testing.
    
    Creates temporary uploads/ and results/ directories.
    Returns the base path.
    """
    base_dir = tmp_path / "data"
    uploads_dir = base_dir / "uploads"
    results_dir = base_dir / "results"
    
    uploads_dir.mkdir(parents=True)
    results_dir.mkdir(parents=True)
    
    return base_dir


@pytest.fixture
def mock_data_definition():
    """Sample data definition for testing."""
    return {
        "value": "target",
        "category": "dynamic_categorical",
        "volume": "dynamic_numerical"
    }


@pytest.fixture
def mock_inference_parameters():
    """Sample inference parameters for testing."""
    return {
        "context_len": 64,
        "horizon_len": 24,
        "use_covariates": False,
        "use_quantiles": False
    }


@pytest.fixture(scope="session")
def test_env():
    """Set up test environment variables."""
    old_env = {}
    test_env_vars = {
        'API_SECRET_KEY': 'test_secret_key',
        'ENVIRONMENT': 'test',
        'LOG_LEVEL': 'DEBUG'
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
