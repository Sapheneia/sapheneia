"""
Test fixtures for Metrics API tests
"""
import pytest
from fastapi.testclient import TestClient
from metrics_api.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)
