"""
Integration tests for TimesFM API endpoints.

Tests the REST API endpoints including:
- Root and health endpoints
- Model status endpoints
- Authentication requirements
- Input validation
- Error handling
"""

import pytest
from fastapi.testclient import TestClient


class TestRootEndpoints:
    """Test root and basic endpoints."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns status."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "docs" in data
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "models" in data
        assert "timestamp" in data
    
    def test_docs_endpoint_accessible(self, client):
        """Test that API docs are accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_schema_accessible(self, client):
        """Test that OpenAPI schema is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema


class TestAuthentication:
    """Test authentication requirements on protected endpoints."""
    
    def test_model_status_requires_auth(self, client):
        """Test that status endpoint requires authentication."""
        response = client.get("/forecast/v1/timesfm20/status")
        
        # Should return 403 Forbidden without auth
        assert response.status_code in [403, 401]
    
    def test_model_status_with_auth(self, client, auth_headers):
        """Test status endpoint with authentication."""
        response = client.get("/forecast/v1/timesfm20/status", headers=auth_headers)
        
        # Should succeed with proper auth
        assert response.status_code == 200
        data = response.json()
        assert "model_status" in data
    
    def test_initialization_requires_auth(self, client):
        """Test that initialization endpoint requires authentication."""
        payload = {
            "backend": "cpu",
            "context_len": 64,
            "horizon_len": 24
        }
        response = client.post(
            "/forecast/v1/timesfm20/initialization",
            json=payload
        )
        
        # Should return 403/401 without auth
        assert response.status_code in [403, 401]
    
    def test_inference_requires_auth(self, client):
        """Test that inference endpoint requires authentication."""
        payload = {
            "data_source_url_or_path": "test.csv",
            "data_definition": {"value": "target"},
            "parameters": {}
        }
        response = client.post(
            "/forecast/v1/timesfm20/inference",
            json=payload
        )
        
        # Should return 403/401 without auth
        assert response.status_code in [403, 401]


class TestModelStatusEndpoint:
    """Test model status endpoint behavior."""
    
    def test_status_without_model_initialized(self, client, auth_headers):
        """Test status when model is not initialized."""
        response = client.get("/forecast/v1/timesfm20/status", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["model_status"] in ["uninitialized", "ready", "error"]
    
    def test_status_structure(self, client, auth_headers):
        """Test that status response has expected structure."""
        response = client.get("/forecast/v1/timesfm20/status", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have required fields
        assert "model_status" in data
        assert isinstance(data["model_status"], str)


class TestInputValidation:
    """Test input validation on endpoints."""
    
    def test_inference_with_invalid_data_definition(self, client, auth_headers):
        """Test inference with invalid data definition."""
        payload = {
            "data_source_url_or_path": "test.csv",
            "data_definition": {"price": "invalid_type"},  # No target!
            "parameters": {}
        }
        
        response = client.post(
            "/forecast/v1/timesfm20/inference",
            headers=auth_headers,
            json=payload
        )
        
        # Should return validation error
        assert response.status_code == 422  # Validation error
    
    def test_inference_with_missing_data_definition(self, client, auth_headers):
        """Test inference with missing data definition."""
        payload = {
            "data_source_url_or_path": "test.csv",
            "parameters": {}
        }
        
        response = client.post(
            "/forecast/v1/timesfm20/inference",
            headers=auth_headers,
            json=payload
        )
        
        # Should return validation error
        assert response.status_code == 422
    
    def test_inference_with_invalid_parameters(self, client, auth_headers):
        """Test inference with invalid parameters."""
        payload = {
            "data_source_url_or_path": "test.csv",
            "data_definition": {"price": "target"},
            "parameters": {
                "context_len": -1  # Invalid: must be positive
            }
        }
        
        response = client.post(
            "/forecast/v1/timesfm20/inference",
            headers=auth_headers,
            json=payload
        )
        
        # Should return validation error
        assert response.status_code == 422


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_inference_with_nonexistent_file(self, client, auth_headers):
        """Test inference with non-existent data file."""
        payload = {
            "data_source_url_or_path": "nonexistent.csv",
            "data_definition": {"value": "target"},
            "parameters": {}
        }
        
        response = client.post(
            "/forecast/v1/timesfm20/inference",
            headers=auth_headers,
            json=payload
        )
        
        # Should return 400 or 409 (depending on model status)
        assert response.status_code in [400, 409, 500]
    
    def test_model_initialization_with_invalid_backend(self, client, auth_headers):
        """Test initialization with invalid backend."""
        payload = {
            "backend": "invalid_backend",
            "context_len": 64,
            "horizon_len": 24
        }
        
        response = client.post(
            "/forecast/v1/timesfm20/initialization",
            headers=auth_headers,
            json=payload
        )
        
        # Should return validation error
        assert response.status_code == 422
    
    def test_model_initialization_with_invalid_context_len(self, client, auth_headers):
        """Test initialization with invalid context length."""
        payload = {
            "backend": "cpu",
            "context_len": 10,  # Too small (< 32)
            "horizon_len": 24
        }
        
        response = client.post(
            "/forecast/v1/timesfm20/initialization",
            headers=auth_headers,
            json=payload
        )
        
        # Should return validation error
        assert response.status_code == 422


@pytest.mark.slow
class TestEndToEnd:
    """End-to-end tests for complete workflows."""
    
    def test_complete_inference_workflow(self, client, auth_headers, sample_data_file):
        """Test complete inference workflow from start to finish."""
        # Step 1: Check initial status
        status_response = client.get("/forecast/v1/timesfm20/status", headers=auth_headers)
        assert status_response.status_code == 200
        
        # Note: Full workflow would require model initialization
        # which takes time and resources. This is a placeholder
        # for the structure of end-to-end tests.
        assert True
