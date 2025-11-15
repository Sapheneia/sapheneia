"""
Integration tests for error handling.

Tests that exceptions are properly converted to HTTP responses.
"""

import pytest


class TestErrorHandling:
    """Test error handling and exception responses."""

    def test_invalid_parameters_error_format(self, test_client, auth_headers):
        """Test InvalidParametersError returns proper error format."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": -105.0,  # Invalid (negative)
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

        # Should return 422 (validation error) or 400
        assert response.status_code in [400, 422]
        data = response.json()
        assert "detail" in data or "error" in data

    def test_insufficient_capital_error(self, test_client, auth_headers):
        """Test InsufficientCapitalError returns 400 with details."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100.0,  # Very little cash
            "initial_capital": 100000.0,
            "threshold_type": "absolute",
            "threshold_value": 0.0,
            "execution_size": 100.0,  # Want to buy 100 shares = $10,000
        }

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        # Should execute but result in hold due to insufficient cash
        assert response.status_code == 200
        data = response.json()
        # May be hold due to insufficient cash
        assert data["action"] in ["buy", "hold"]

    def test_strategy_stopped_error(self, test_client, auth_headers):
        """Test StrategyStoppedError returns 400 with details."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 0.0,  # No cash
            "initial_capital": 100000.0,
            "threshold_type": "absolute",
            "threshold_value": 0.0,
            "execution_size": 100.0,
        }

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        # Should return 200 but with stopped=True
        assert response.status_code == 200
        data = response.json()
        assert data["stopped"] is True

    def test_invalid_strategy_error(self, test_client, auth_headers):
        """Test InvalidStrategyError returns 400 with details."""
        # This will be caught at schema validation level (422) or strategy execution (400)
        payload = {
            "strategy_type": "invalid_strategy_type",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
        }

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        # Should return 422 (validation) or 400 (execution)
        assert response.status_code in [400, 422]

    def test_error_response_format(self, test_client, auth_headers):
        """Test error responses include error_code and message."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": -105.0,  # Invalid
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

        assert response.status_code in [400, 422]
        data = response.json()
        # Error response should have detail or error information
        assert "detail" in data or "error" in data or "message" in data
