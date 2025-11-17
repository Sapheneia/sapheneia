"""
Test fixtures for Metrics tests
"""
import pytest
from fastapi.testclient import TestClient
from metrics.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)
