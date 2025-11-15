"""
Integration tests for health check endpoints.

Tests root and health endpoints.
"""

import pytest


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, test_client):
        """Test root endpoint returns status."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "service" in data
        assert "version" in data
        assert "docs" in data

    def test_health_endpoint(self, test_client):
        """Test health endpoint returns detailed status."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data
        assert "available_strategies" in data
        assert isinstance(data["available_strategies"], list)
        assert "threshold" in data["available_strategies"]
        assert "return" in data["available_strategies"]
        assert "quantile" in data["available_strategies"]

    def test_health_endpoints_no_auth_required(self, test_client):
        """Test health endpoints don't require authentication."""
        # Root endpoint
        response = test_client.get("/")
        assert response.status_code == 200

        # Health endpoint
        response = test_client.get("/health")
        assert response.status_code == 200
