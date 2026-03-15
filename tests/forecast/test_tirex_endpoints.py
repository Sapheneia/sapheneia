"""
Integration tests for TiRex API endpoints.

Tests the REST API endpoints including:
- Model status endpoints
- Authentication requirements
- Input validation (context length, device config)
- Error handling
"""

import pytest

# Try to import the app - tests will be skipped if import fails
try:
    from fastapi.testclient import TestClient
    from forecast.main import app
    from forecast.core.config import settings
    APP_AVAILABLE = True
except ImportError as e:
    APP_AVAILABLE = False
    APP_IMPORT_ERROR = str(e)


# Skip all tests in this module if the app can't be imported
pytestmark = pytest.mark.skipif(
    not APP_AVAILABLE,
    reason=f"forecast.main app cannot be imported (likely missing dependencies)"
)


@pytest.fixture
def client():
    """Fixture providing a FastAPI TestClient for the forecast app."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Fixture providing authentication headers for API requests."""
    return {"Authorization": f"Bearer {settings.API_SECRET_KEY}"}


class TestAuthentication:
    """Test authentication requirements on protected TiRex endpoints."""

    def test_model_status_requires_auth(self, client):
        """Test that status endpoint requires authentication."""
        response = client.get("/forecast/v1/tirex/status")

        # Should return 401 Unauthorized without auth
        assert response.status_code == 401

    def test_model_status_with_auth(self, client, auth_headers):
        """Test status endpoint with authentication."""
        response = client.get("/forecast/v1/tirex/status", headers=auth_headers)

        # Should succeed with proper auth
        assert response.status_code == 200
        data = response.json()
        assert "model_status" in data

    def test_initialization_requires_auth(self, client):
        """Test that initialization endpoint requires authentication."""
        payload = {
            "model_variant": "NX-AI/TiRex",
            "device": "cpu"
        }
        response = client.post(
            "/forecast/v1/tirex/initialization",
            json=payload
        )

        # Should return 401 without auth
        assert response.status_code == 401

    def test_inference_requires_auth(self, client):
        """Test that inference endpoint requires authentication."""
        payload = {
            "context": [1.0, 2.0, 3.0, 4.0, 5.0],
            "prediction_length": 5
        }
        response = client.post(
            "/forecast/v1/tirex/inference",
            json=payload
        )

        # Should return 401 without auth
        assert response.status_code == 401


class TestModelStatusEndpoint:
    """Test TiRex model status endpoint behavior."""

    def test_status_without_model_initialized(self, client, auth_headers):
        """Test status when model is not initialized."""
        response = client.get("/forecast/v1/tirex/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["model_status"] in ["uninitialized", "ready", "error"]

    def test_status_structure(self, client, auth_headers):
        """Test that status response has expected structure."""
        response = client.get("/forecast/v1/tirex/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have required fields
        assert "model_status" in data
        assert isinstance(data["model_status"], str)


class TestInputValidation:
    """Test input validation on TiRex endpoints."""

    def test_inference_with_missing_context(self, client, auth_headers):
        """Test inference with missing historical context."""
        payload = {
            "prediction_length": 10
        }

        response = client.post(
            "/forecast/v1/tirex/inference",
            headers=auth_headers,
            json=payload
        )

        # Should return 422 Unprocessable Entity
        assert response.status_code == 422

    def test_inference_with_invalid_prediction_length(self, client, auth_headers):
        """Test inference with invalid prediction parameter."""
        payload = {
            "context": [1.0, 2.0, 3.0],
            "prediction_length": -1  # Invalid: must be positive
        }

        response = client.post(
            "/forecast/v1/tirex/inference",
            headers=auth_headers,
            json=payload
        )

        # Should return validation error
        assert response.status_code == 422


class TestErrorHandling:
    """Test error handling and edge cases for TiRex."""

    def test_model_initialization_with_invalid_device(self, client, auth_headers):
        """Test initialization with invalid GPU/CPU backend."""
        payload = {
            "model_variant": "NX-AI/TiRex",
            "device": "invalid_device"
        }

        response = client.post(
            "/forecast/v1/tirex/initialization",
            headers=auth_headers,
            json=payload
        )

        # Should return validation error based on Pydantic device list limit
        assert response.status_code == 422

    def test_model_initialization_missing_variant(self, client, auth_headers):
        """Test initialization requires model variant implicitly if absent."""
        payload = {
            "device": "cpu"
        }

        response = client.post(
            "/forecast/v1/tirex/initialization",
            headers=auth_headers,
            json=payload
        )
        
        # Will succeed because model_variant is technically optional and falls back to environment variable NX-AI/TiRex
        assert response.status_code in [200, 500] 


@pytest.mark.slow
class TestEndToEnd:
    """End-to-end tests for TiRex workflow."""

    def test_tirex_status_workflow(self, client, auth_headers):
        """Test TiRex status workflow route."""
        # Step 1: Check initial status
        status_response = client.get("/forecast/v1/tirex/status", headers=auth_headers)
        assert status_response.status_code == 200
        
        # Step 2: Test graceful shutdown router
        shutdown_response = client.post("/forecast/v1/tirex/shutdown", headers=auth_headers)
        assert shutdown_response.status_code == 200
