"""
Performance tests for trading strategies API.

Tests response times to ensure they meet the <100ms requirement for typical requests.
"""

import time
import pytest
from fastapi.testclient import TestClient
from trading.main import app
from trading.core.config import settings

test_client = TestClient(app)


class TestPerformance:
    """Performance tests for trading API endpoints."""

    @pytest.fixture
    def auth_headers(self):
        """Authentication headers for testing."""
        return {"Authorization": f"Bearer {settings.TRADING_API_KEY}"}

    def test_threshold_strategy_performance(self, auth_headers):
        """Test threshold strategy response time <100ms and X-Process-Time header."""
        payload = {
            "strategy_type": "threshold",
            "forecast_price": 105.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "threshold_type": "absolute",
            "threshold_value": 2.0,
            "execution_size": 100.0,
        }

        start_time = time.time()
        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )
        elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        assert response.status_code == 200
        assert elapsed_time < 100, f"Response time {elapsed_time:.2f}ms exceeds 100ms"

        # Verify X-Process-Time header is present
        assert "X-Process-Time" in response.headers
        process_time = float(response.headers["X-Process-Time"])
        assert process_time > 0, "Process time should be positive"
        assert process_time < 200, "Process time should be reasonable (<200ms)"

    def test_return_strategy_performance(self, auth_headers):
        """Test return strategy response time <100ms."""
        payload = {
            "strategy_type": "return",
            "forecast_price": 108.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "position_sizing": "fixed",
            "threshold_value": 0.05,
            "execution_size": 10.0,
        }

        start_time = time.time()
        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )
        elapsed_time = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert elapsed_time < 100, f"Response time {elapsed_time:.2f}ms exceeds 100ms"

    def test_quantile_strategy_performance(self, auth_headers):
        """Test quantile strategy response time <100ms."""
        # Generate sample OHLC data
        base_price = 100.0
        ohlc_length = 20
        open_history = [base_price + i * 0.1 for i in range(ohlc_length)]
        high_history = [base_price + i * 0.1 + 5.0 for i in range(ohlc_length)]
        low_history = [base_price + i * 0.1 - 5.0 for i in range(ohlc_length)]
        close_history = [base_price + i * 0.1 + 2.0 for i in range(ohlc_length)]

        payload = {
            "strategy_type": "quantile",
            "forecast_price": 92.0,
            "current_price": 100.0,
            "current_position": 0.0,
            "available_cash": 100000.0,
            "initial_capital": 100000.0,
            "which_history": "close",
            "window_history": 20,
            "quantile_signals": {
                "1": {"range": [0, 20], "signal": "buy", "multiplier": 1.0},
                "2": {"range": [80, 100], "signal": "sell", "multiplier": 1.0},
            },
            "position_sizing": "fixed",
            "execution_size": 10.0,
            "open_history": open_history,
            "high_history": high_history,
            "low_history": low_history,
            "close_history": close_history,
        }

        start_time = time.time()
        response = test_client.post(
            "/trading/execute", json=payload, headers=auth_headers
        )
        elapsed_time = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert elapsed_time < 100, f"Response time {elapsed_time:.2f}ms exceeds 100ms"

    def test_strategies_endpoint_performance(self):
        """Test strategies endpoint response time <50ms and X-Process-Time header."""
        start_time = time.time()
        response = test_client.get("/trading/strategies")
        elapsed_time = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert elapsed_time < 50, f"Response time {elapsed_time:.2f}ms exceeds 50ms"

        # Verify X-Process-Time header is present
        assert "X-Process-Time" in response.headers
        process_time = float(response.headers["X-Process-Time"])
        assert process_time > 0, "Process time should be positive"
        assert process_time < 100, "Process time should be reasonable (<100ms)"

    def test_health_endpoint_performance(self):
        """Test health endpoint response time <50ms and X-Process-Time header."""
        start_time = time.time()
        response = test_client.get("/health")
        elapsed_time = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert elapsed_time < 50, f"Response time {elapsed_time:.2f}ms exceeds 50ms"

        # Verify X-Process-Time header is present
        assert "X-Process-Time" in response.headers
        process_time = float(response.headers["X-Process-Time"])
        assert process_time > 0, "Process time should be positive"
        assert process_time < 100, "Process time should be reasonable (<100ms)"

    def test_process_time_header_format(self, auth_headers):
        """Test that X-Process-Time header is properly formatted."""
        response = test_client.get("/health")

        assert response.status_code == 200
        assert "X-Process-Time" in response.headers

        process_time_str = response.headers["X-Process-Time"]
        # Should be a float string with up to 3 decimal places
        process_time = float(process_time_str)
        assert process_time >= 0, "Process time should be non-negative"
        assert (
            "." in process_time_str or process_time == 0
        ), "Should have decimal format"

    def test_process_time_header_present_in_all_responses(self, auth_headers):
        """Test that X-Process-Time header is present in all endpoint responses."""
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
                "X-Process-Time" in response.headers
            ), f"Missing X-Process-Time for {path}"

            # Verify it's a valid float
            process_time = float(response.headers["X-Process-Time"])
            assert process_time >= 0, f"Process time should be non-negative for {path}"
