"""
Integration tests for request ID tracking.

Tests that request IDs are generated, included in headers, logs, and error responses.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from trading.main import app
from trading.core.config import settings

test_client = TestClient(app)


class TestRequestID:
    """Test request ID generation and tracking."""

    @pytest.fixture
    def auth_headers(self):
        """Authentication headers for testing."""
        return {"Authorization": f"Bearer {settings.TRADING_API_KEY}"}

    def test_request_id_in_response_headers(self, auth_headers):
        """Test that X-Request-ID header is present in all responses."""
        response = test_client.get("/health", headers=auth_headers)

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]

        # Verify it's a valid UUID
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Request ID '{request_id}' is not a valid UUID")

    def test_request_id_is_unique(self, auth_headers):
        """Test that each request gets a unique request ID."""
        request_ids = set()

        # Make multiple requests
        for _ in range(10):
            response = test_client.get("/health", headers=auth_headers)
            assert response.status_code == 200
            request_id = response.headers["X-Request-ID"]
            request_ids.add(request_id)

        # All request IDs should be unique
        assert len(request_ids) == 10, "Request IDs should be unique"

    def test_request_id_in_error_responses(self, auth_headers):
        """Test that request ID is included in error response headers."""
        # Make a request that will fail (invalid strategy type - Pydantic validation)
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

        # Should get a validation error (422)
        assert response.status_code == 422

        # Check that request ID header is present (this is what we're testing)
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]

        # Verify it's a valid UUID
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Request ID '{request_id}' is not a valid UUID")

        # Note: Pydantic validation errors return FastAPI's standard format
        # which doesn't include request_id in body, but header is always present

    def test_request_id_in_trading_exception_response(self, auth_headers):
        """Test that request ID is included in TradingException responses."""
        # Make a request that will trigger a TradingException
        # Using invalid parameters that will fail validation
        payload = {
            "strategy_type": "threshold",
            "forecast_price": 105.0,
            "current_price": 0.0,  # Invalid: must be > 0
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

        # Should get an error response
        assert response.status_code in [400, 422]

        # Check that request ID header is present
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]

        # Verify request ID is in error response
        data = response.json()
        if "details" in data and isinstance(data["details"], dict):
            assert data["details"].get("request_id") == request_id

    def test_request_id_in_all_endpoints(self, auth_headers):
        """Test that request ID is present in all endpoint responses."""
        endpoints = [
            ("GET", "/health"),
            ("GET", "/"),
            ("GET", "/trading/strategies"),
            ("GET", "/trading/status"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path, headers=auth_headers)
            else:
                response = test_client.post(path, headers=auth_headers)

            assert response.status_code in [200, 429], f"Failed for {method} {path}"
            assert (
                "X-Request-ID" in response.headers
            ), f"Missing X-Request-ID for {path}"

            # Verify it's a valid UUID
            request_id = response.headers["X-Request-ID"]
            try:
                uuid.UUID(request_id)
            except ValueError:
                pytest.fail(f"Request ID '{request_id}' is not a valid UUID for {path}")
