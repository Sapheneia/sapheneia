"""
Integration tests for /execute endpoint.

Tests the full request/response cycle for strategy execution.
"""

import pytest
from trading.schemas.schema import StrategyResponse


class TestExecuteEndpoint:
    """Test POST /trading/execute endpoint."""

    def test_threshold_strategy_execution(self, test_client, auth_headers):
        """Test threshold strategy execution with valid request."""
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
        data = response.json()
        assert "action" in data
        assert "size" in data
        assert "value" in data
        assert "reason" in data
        assert "available_cash" in data
        assert "position_after" in data
        assert "stopped" in data
        assert data["action"] in ["buy", "sell", "hold"]

    def test_return_strategy_execution(self, test_client, auth_headers):
        """Test return strategy execution with valid request."""
        payload = {
            "strategy_type": "return",
            "forecast_price": 108.0,
            "current_price": 100.0,
            "current_position": 100.0,
            "available_cash": 90000.0,
            "initial_capital": 100000.0,
            "position_sizing": "proportional",
            "threshold_value": 0.05,
            "execution_size": 10.0,
        }

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] in ["buy", "sell", "hold"]

    def test_quantile_strategy_execution(
        self, test_client, auth_headers, sample_ohlc_data
    ):
        """Test quantile strategy execution with valid request."""
        payload = {
            "strategy_type": "quantile",
            "forecast_price": 110.0,
            "current_price": 100.0,
            "current_position": 100.0,
            "available_cash": 90000.0,
            "initial_capital": 100000.0,
            "which_history": "close",
            "window_history": 20,
            "quantile_signals": {
                1: {"range": [0, 5], "signal": "sell", "multiplier": 1.0},
                2: {"range": [90, 95], "signal": "buy", "multiplier": 0.75},
            },
            "position_sizing": "fixed",
            "execution_size": 100.0,
        }
        payload.update(sample_ohlc_data)

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] in ["buy", "sell", "hold"]

    def test_invalid_strategy_type(self, test_client, auth_headers):
        """Test invalid strategy type returns 422 validation error."""
        payload = {
            "strategy_type": "invalid_strategy",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
        }

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_missing_required_parameters(self, test_client, auth_headers):
        """Test missing required parameters returns 422 validation error."""
        payload = {
            "strategy_type": "threshold",
            # Missing forecast_price, current_price, etc.
        }

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        assert response.status_code == 422

    def test_negative_prices(self, test_client, auth_headers):
        """Test negative prices returns 422 validation error."""
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

        assert response.status_code == 422

    def test_negative_position(self, test_client, auth_headers):
        """Test negative position returns 422 validation error (long-only)."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": -10.0,  # Invalid (long-only)
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "threshold_type": "absolute",
            "threshold_value": 0.0,
            "execution_size": 100.0,
        }

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        assert response.status_code == 422

    def test_invalid_threshold_type(self, test_client, auth_headers):
        """Test invalid threshold_type returns 422 validation error."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "threshold_type": "invalid_type",
            "threshold_value": 0.0,
            "execution_size": 100.0,
        }

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        assert response.status_code == 422

    def test_invalid_position_sizing(self, test_client, auth_headers):
        """Test invalid position_sizing returns 422 validation error."""
        payload = {
            "strategy_type": "return",
            "forecast_price": 108.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "position_sizing": "invalid_sizing",
            "threshold_value": 0.05,
            "execution_size": 10.0,
        }

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        assert response.status_code == 422

    def test_invalid_quantile_signals_structure(
        self, test_client, auth_headers, sample_ohlc_data
    ):
        """Test invalid quantile_signals structure returns 422 validation error."""
        payload = {
            "strategy_type": "quantile",
            "forecast_price": 110.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "which_history": "close",
            "window_history": 20,
            "quantile_signals": "invalid",  # Should be dict
            "position_sizing": "fixed",
            "execution_size": 100.0,
        }
        payload.update(sample_ohlc_data)

        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )

        assert response.status_code == 422

    def test_response_schema_validation(self, test_client, auth_headers):
        """Test response matches StrategyResponse schema."""
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
        data = response.json()

        # Validate all required fields are present
        required_fields = [
            "action",
            "size",
            "value",
            "reason",
            "available_cash",
            "position_after",
            "stopped",
        ]
        for field in required_fields:
            assert field in data

        # Validate field types
        assert isinstance(data["action"], str)
        assert isinstance(data["size"], (int, float))
        assert isinstance(data["value"], (int, float))
        assert isinstance(data["reason"], str)
        assert isinstance(data["available_cash"], (int, float))
        assert isinstance(data["position_after"], (int, float))
        assert isinstance(data["stopped"], bool)
