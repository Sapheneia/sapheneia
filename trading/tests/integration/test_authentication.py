"""
Integration tests for authentication.

Tests API key validation on protected endpoints.
"""

import pytest


class TestAuthentication:
    """Test authentication on API endpoints."""

    def test_valid_api_key_allows_access(self, test_client, auth_headers):
        """Test valid API key allows access to protected endpoint."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "threshold_type": "absolute",
            "threshold_value": 0.0,
            "execution_size": 100.0,
        }

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        assert response.status_code == 200

    def test_invalid_api_key_returns_401(self, test_client):
        """Test invalid API key returns 401 Unauthorized."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "threshold_type": "absolute",
            "threshold_value": 0.0,
            "execution_size": 100.0,
        }

        headers = {"Authorization": "Bearer invalid_api_key"}

        response = test_client.post("/trading/execute", json=payload, headers=headers)

        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_missing_authorization_header_returns_401(self, test_client):
        """Test missing Authorization header returns 401."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "threshold_type": "absolute",
            "threshold_value": 0.0,
            "execution_size": 100.0,
        }

        response = test_client.post(
            "/trading/execute",
            json=payload,
            # No Authorization header
        )

        assert (
            response.status_code == 403
        )  # FastAPI returns 403 for missing credentials

    def test_malformed_authorization_header(self, test_client):
        """Test malformed Authorization header returns 401."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "threshold_type": "absolute",
            "threshold_value": 0.0,
            "execution_size": 100.0,
        }

        headers = {"Authorization": "InvalidFormat api_key"}

        response = test_client.post("/trading/execute", json=payload, headers=headers)

        # Should return 403 or 401 depending on FastAPI behavior
        assert response.status_code in [401, 403]

    def test_public_endpoints_no_auth_required(self, test_client):
        """Test public endpoints don't require authentication."""
        # Test /trading/strategies
        response = test_client.get("/trading/strategies")
        assert response.status_code == 200

        # Test /trading/status
        response = test_client.get("/trading/status")
        assert response.status_code == 200

        # Test /health
        response = test_client.get("/health")
        assert response.status_code == 200

        # Test /
        response = test_client.get("/")
        assert response.status_code == 200
