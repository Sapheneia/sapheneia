"""
Tests for orchestration/clients modules.

Tests MetricsClient, TradingClient, and PortfolioManager.
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
import httpx

from orchestration.clients.metrics_client import (
    MetricsClient,
    MetricsResponse,
    CircuitState,
    prices_to_returns,
)
from orchestration.clients.trading_client import (
    TradingClient,
    TradeResult,
    TradeAction,
    PortfolioState,
    PortfolioManager,
    StrategyType,
)


# =============================================================================
# METRICS CLIENT TESTS
# =============================================================================

class TestMetricsResponse:
    """Tests for MetricsResponse dataclass."""

    def test_from_dict(self):
        """Should create MetricsResponse from dict."""
        data = {
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.15,
            "cagr": 0.12,
            "calmar_ratio": 0.8,
            "win_rate": 0.55,
        }
        response = MetricsResponse.from_dict(data)

        assert response.sharpe_ratio == 1.5
        assert response.max_drawdown == -0.15
        assert response.cagr == 0.12
        assert response.calmar_ratio == 0.8
        assert response.win_rate == 0.55

    def test_from_dict_missing_keys(self):
        """Should handle missing keys with defaults."""
        data = {"sharpe_ratio": 1.0}
        response = MetricsResponse.from_dict(data)

        assert response.sharpe_ratio == 1.0
        assert response.max_drawdown == 0.0
        assert response.cagr == 0.0

    def test_to_dict(self):
        """Should convert to dict."""
        response = MetricsResponse(
            sharpe_ratio=1.5,
            max_drawdown=-0.1,
            cagr=0.15,
            calmar_ratio=1.5,
            win_rate=0.6,
        )
        d = response.to_dict()

        assert d["sharpe_ratio"] == 1.5
        assert d["max_drawdown"] == -0.1


class TestPricesToReturns:
    """Tests for prices_to_returns function."""

    def test_basic_conversion(self):
        """Should convert prices to returns."""
        prices = [100.0, 102.0, 101.0, 105.0]
        returns = prices_to_returns(prices)

        assert len(returns) == 3
        assert abs(returns[0] - 0.02) < 0.001  # 2% gain
        assert abs(returns[1] - (-0.0098)) < 0.001  # ~1% loss
        assert abs(returns[2] - 0.0396) < 0.001  # ~4% gain

    def test_empty_prices(self):
        """Should return empty for empty prices."""
        assert prices_to_returns([]) == []

    def test_single_price(self):
        """Should return empty for single price."""
        assert prices_to_returns([100.0]) == []

    def test_handles_zero_price(self):
        """Should handle zero price (division by zero)."""
        prices = [100.0, 0.0, 50.0]
        returns = prices_to_returns(prices)

        assert len(returns) == 2
        assert returns[1] == 0.0  # 0/0 case

    def test_handles_nan(self):
        """Should handle NaN in prices."""
        prices = [100.0, float('nan'), 102.0]
        returns = prices_to_returns(prices)

        assert len(returns) == 2
        # NaN handling

    def test_caps_extreme_loss_at_minus_one(self):
        """Should cap extreme losses at -100% (total loss)."""
        # Total loss: $100 -> $0 = -100%
        prices = [100.0, 0.0]
        returns = prices_to_returns(prices)

        assert len(returns) == 1
        assert returns[0] == -1.0  # Exactly at -100% cap

        # Even more extreme: would be < -100% without cap
        # This can't happen in reality (price can't go negative)
        # but the cap prevents math errors if bad data comes through

    def test_caps_extreme_gain_at_ten(self):
        """Should cap extreme gains at +1000%."""
        # 1900% gain: $10 -> $200
        prices = [10.0, 200.0]
        returns = prices_to_returns(prices)

        assert len(returns) == 1
        assert returns[0] == 10.0  # Capped at +1000%

    def test_normal_returns_not_capped(self):
        """Normal returns within bounds should not be capped."""
        # 50% gain (within bounds)
        prices = [100.0, 150.0]
        returns = prices_to_returns(prices)
        assert abs(returns[0] - 0.5) < 0.001

        # 50% loss (within bounds)
        prices = [100.0, 50.0]
        returns = prices_to_returns(prices)
        assert abs(returns[0] - (-0.5)) < 0.001

    def test_returns_at_cap_boundaries(self):
        """Returns exactly at cap boundaries should not be capped further."""
        # Exactly -100% (price goes to 0): (0-100)/100 = -1.0
        prices = [100.0, 0.0]
        returns = prices_to_returns(prices)
        assert returns[0] == -1.0  # Exactly at lower bound

        # Exactly +1000%: (110-10)/10 = 10.0
        prices = [10.0, 110.0]
        returns = prices_to_returns(prices)
        assert returns[0] == 10.0  # Exactly at upper bound

        # Verify division by zero is handled (previous price = 0)
        prices = [0.0, 100.0]
        returns = prices_to_returns(prices)
        assert returns[0] == 0.0  # Zero divisor returns 0


class TestMetricsClient:
    """Tests for MetricsClient class."""

    @pytest.fixture
    def client(self):
        """Create client for testing."""
        return MetricsClient(
            base_url="http://test:8000",
            timeout=5.0,
            max_retries=2,
        )

    @pytest.mark.asyncio
    async def test_compute_metrics_success(self, client):
        """Should compute metrics successfully."""
        mock_response_data = {
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.12,
            "cagr": 0.18,
            "calmar_ratio": 1.5,
            "win_rate": 0.58,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await client.compute_metrics([0.01, -0.02, 0.03, 0.01])

            assert result.sharpe_ratio == 1.5
            assert result.max_drawdown == -0.12

    @pytest.mark.asyncio
    async def test_compute_metrics_empty_returns(self, client):
        """Should return fallback for empty returns."""
        result = await client.compute_metrics([])

        assert result.sharpe_ratio == 0.0
        assert result.max_drawdown == 0.0

    @pytest.mark.asyncio
    async def test_compute_metrics_single_return(self, client):
        """Should return fallback for single return."""
        result = await client.compute_metrics([0.01])

        assert result.sharpe_ratio == 0.0

    @pytest.mark.asyncio
    async def test_compute_metrics_http_error(self, client):
        """Should return fallback on HTTP error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=Mock(status_code=500),
            )
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await client.compute_metrics([0.01, -0.02, 0.03])

            assert result.sharpe_ratio == 0.0

    def test_circuit_breaker_initial_state(self, client):
        """Circuit breaker should start closed."""
        assert client.circuit_state == CircuitState.CLOSED


# =============================================================================
# TRADING CLIENT TESTS
# =============================================================================

class TestTradeResult:
    """Tests for TradeResult dataclass."""

    def test_from_dict(self):
        """Should create TradeResult from dict."""
        data = {
            "action": "buy",
            "size": 10.0,
            "value": 4500.0,
            "reason": "Forecast bullish",
            "available_cash": 45000.0,
            "position_after": 10.0,
            "stopped": False,
        }
        result = TradeResult.from_dict(data)

        assert result.action == TradeAction.BUY
        assert result.size == 10.0
        assert result.value == 4500.0

    def test_from_dict_with_metadata(self):
        """Should include metadata."""
        data = {"action": "hold", "size": 0.0, "value": 0.0,
                "reason": "", "available_cash": 50000.0,
                "position_after": 0.0, "stopped": False}
        metadata = {
            "forecast_price": 455.0,
            "current_price": 450.0,
            "timestamp": "2023-01-15",
        }
        result = TradeResult.from_dict(data, metadata)

        assert result.forecast_price == 455.0
        assert result.current_price == 450.0
        assert result.timestamp == "2023-01-15"

    def test_hold_class_method(self):
        """Should create HOLD result."""
        portfolio = PortfolioState(position=10.0, cash=45000.0, initial_capital=100000.0)
        result = TradeResult.hold(portfolio, "Test hold")

        assert result.action == TradeAction.HOLD
        assert result.size == 0.0
        assert result.position_after == 10.0
        assert result.available_cash == 45000.0


class TestPortfolioState:
    """Tests for PortfolioState dataclass."""

    def test_calculate_total_value(self):
        """Should calculate total value correctly."""
        portfolio = PortfolioState(position=100.0, cash=50000.0, initial_capital=100000.0)
        total = portfolio.calculate_total_value(current_price=500.0)

        assert total == 100000.0  # 100 * 500 + 50000

    def test_to_dict(self):
        """Should convert to dict."""
        portfolio = PortfolioState(position=10.0, cash=45000.0, initial_capital=100000.0)
        d = portfolio.to_dict()

        assert d["position"] == 10.0
        assert d["cash"] == 45000.0
        assert d["initial_capital"] == 100000.0

    def test_from_dict(self):
        """Should create from dict."""
        data = {"position": 10.0, "cash": 45000.0, "initial_capital": 100000.0}
        portfolio = PortfolioState.from_dict(data)

        assert portfolio.position == 10.0
        assert portfolio.cash == 45000.0


class TestPortfolioManager:
    """Tests for PortfolioManager class."""

    @pytest.fixture
    def manager(self):
        """Create manager for testing."""
        return PortfolioManager(initial_capital=100000.0, checkpoint_interval=5)

    def test_initial_state(self, manager):
        """Manager should start with initial capital."""
        assert manager.portfolio.position == 0.0
        assert manager.portfolio.cash == 100000.0
        assert len(manager.equity_curve) == 1
        assert manager.equity_curve[0] == 100000.0

    def test_apply_trade(self, manager):
        """Should apply trade correctly."""
        trade = TradeResult(
            action=TradeAction.BUY,
            size=10.0,
            value=4500.0,
            reason="Test buy",
            available_cash=95500.0,
            position_after=10.0,
            stopped=False,
        )
        manager.apply_trade(trade, current_price=450.0)

        assert manager.portfolio.position == 10.0
        assert manager.portfolio.cash == 95500.0
        assert len(manager.trades) == 1
        assert len(manager.equity_curve) == 2

    def test_should_checkpoint(self, manager):
        """Should checkpoint at intervals."""
        assert not manager.should_checkpoint()

        # Apply 5 trades
        for i in range(5):
            trade = TradeResult.hold(manager.portfolio, "Test")
            manager.apply_trade(trade, 100.0)

        assert manager.should_checkpoint()

    def test_get_checkpoint(self, manager):
        """Should get checkpoint data."""
        trade = TradeResult(
            action=TradeAction.BUY,
            size=10.0,
            value=4500.0,
            reason="Test",
            available_cash=95500.0,
            position_after=10.0,
            stopped=False,
        )
        manager.apply_trade(trade, 450.0)

        checkpoint = manager.get_checkpoint()

        assert checkpoint["trades_count"] == 1
        assert checkpoint["portfolio"]["position"] == 10.0

    def test_get_trade_summary(self, manager):
        """Should get trade summary."""
        # Add some trades
        buy = TradeResult(
            action=TradeAction.BUY, size=10.0, value=4500.0,
            reason="", available_cash=95500.0, position_after=10.0, stopped=False)
        sell = TradeResult(
            action=TradeAction.SELL, size=5.0, value=2300.0,
            reason="", available_cash=97800.0, position_after=5.0, stopped=False)
        hold = TradeResult.hold(manager.portfolio, "Test")

        manager.apply_trade(buy, 450.0)
        manager.apply_trade(sell, 460.0)
        manager.apply_trade(hold, 455.0)

        summary = manager.get_trade_summary()

        assert summary["total_trades"] == 3
        assert summary["buys"] == 1
        assert summary["sells"] == 1
        assert summary["holds"] == 1

    def test_restore_from_checkpoint_restores_portfolio(self, manager):
        """Should restore portfolio state from checkpoint."""
        checkpoint = {
            "portfolio": {
                "position": 50.0,
                "cash": 45000.0,
                "initial_capital": 100000.0,
            },
            "last_equity": 95000.0,
            "iteration": 25,
        }

        manager.restore_from_checkpoint(checkpoint)

        assert manager.portfolio.position == 50.0
        assert manager.portfolio.cash == 45000.0
        assert manager.portfolio.initial_capital == 100000.0

    def test_restore_from_checkpoint_restores_equity_curve(self, manager):
        """Should restore equity curve from checkpoint."""
        checkpoint = {
            "portfolio": {"position": 0.0, "cash": 100000.0, "initial_capital": 100000.0},
            "last_equity": 95000.0,
            "iteration": 10,
        }

        manager.restore_from_checkpoint(checkpoint)

        assert manager.equity_curve == [95000.0]

    def test_restore_from_checkpoint_restores_iteration_count(self, manager):
        """Should restore iteration count from checkpoint."""
        checkpoint = {
            "portfolio": {"position": 0.0, "cash": 100000.0, "initial_capital": 100000.0},
            "last_equity": 100000.0,
            "iteration": 42,
        }

        manager.restore_from_checkpoint(checkpoint)

        assert manager._iteration_count == 42

    def test_restore_from_checkpoint_handles_partial_checkpoint(self, manager):
        """Should handle checkpoint with missing fields."""
        # Checkpoint without last_equity
        checkpoint = {
            "portfolio": {"position": 10.0, "cash": 90000.0, "initial_capital": 100000.0},
            "iteration": 5,
        }

        manager.restore_from_checkpoint(checkpoint)

        assert manager.portfolio.position == 10.0
        # equity_curve should remain unchanged (initial value)
        assert manager.equity_curve == [100000.0]
        assert manager._iteration_count == 5

    def test_validate_warns_on_negative_position(self, manager, caplog):
        """Should warn when position becomes negative."""
        import logging
        caplog.set_level(logging.WARNING)

        # Manually set invalid state (simulating a bug in trading service)
        manager.portfolio.position = -10.0
        manager.portfolio.cash = 100000.0
        manager._validate_portfolio(current_price=100.0)

        assert "Negative position detected" in caplog.text
        assert "-10.0" in caplog.text

    def test_validate_warns_on_negative_cash(self, manager, caplog):
        """Should warn when cash becomes negative."""
        import logging
        caplog.set_level(logging.WARNING)

        # Manually set invalid state
        manager.portfolio.position = 0.0
        manager.portfolio.cash = -5000.0
        manager._validate_portfolio(current_price=100.0)

        assert "Negative cash detected" in caplog.text
        assert "-5000.0" in caplog.text

    def test_validate_warns_on_zero_total_value(self, manager, caplog):
        """Should warn when total value is zero or negative."""
        import logging
        caplog.set_level(logging.WARNING)

        # Set state where total value is zero
        manager.portfolio.position = 0.0
        manager.portfolio.cash = 0.0
        manager._validate_portfolio(current_price=100.0)

        assert "Total value not positive" in caplog.text

    def test_validate_no_warning_on_valid_state(self, manager, caplog):
        """Should not warn on valid portfolio state."""
        import logging
        caplog.set_level(logging.WARNING)

        # Valid state
        manager.portfolio.position = 10.0
        manager.portfolio.cash = 50000.0
        manager._validate_portfolio(current_price=100.0)

        assert "Negative" not in caplog.text
        assert "not positive" not in caplog.text


class TestTradingClient:
    """Tests for TradingClient class."""

    @pytest.fixture
    def client(self):
        """Create client for testing."""
        return TradingClient(
            base_url="http://test:9000",
            api_key="test-key",
            timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_execute_signal_success(self, client):
        """Should execute signal successfully."""
        mock_response_data = {
            "action": "buy",
            "size": 10.0,
            "value": 4521.0,
            "reason": "Forecast bullish",
            "available_cash": 45479.0,
            "position_after": 110.0,
            "stopped": False,
        }

        portfolio = PortfolioState(position=100.0, cash=50000.0, initial_capital=100000.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await client.execute_signal(
                forecast_price=455.0,
                current_price=450.0,
                portfolio=portfolio,
            )

            assert result.action == TradeAction.BUY
            assert result.size == 10.0
            assert result.position_after == 110.0

    @pytest.mark.asyncio
    async def test_execute_signal_http_error(self, client):
        """Should return HOLD on HTTP error."""
        portfolio = PortfolioState(position=100.0, cash=50000.0, initial_capital=100000.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=Mock(status_code=500),
            )
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await client.execute_signal(
                forecast_price=455.0,
                current_price=450.0,
                portfolio=portfolio,
            )

            assert result.action == TradeAction.HOLD
            assert "error" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_execute_signal_connection_error(self, client):
        """Should return HOLD on connection error."""
        portfolio = PortfolioState(position=0.0, cash=100000.0, initial_capital=100000.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await client.execute_signal(
                forecast_price=455.0,
                current_price=450.0,
                portfolio=portfolio,
            )

            assert result.action == TradeAction.HOLD
            assert "unavailable" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_execute_signal_includes_auth_header(self, client):
        """Should include auth header when API key set."""
        portfolio = PortfolioState(position=0.0, cash=100000.0, initial_capital=100000.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = {
                "action": "hold", "size": 0.0, "value": 0.0,
                "reason": "", "available_cash": 100000.0,
                "position_after": 0.0, "stopped": False}
            mock_response.raise_for_status = Mock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await client.execute_signal(
                forecast_price=450.0,
                current_price=450.0,
                portfolio=portfolio,
            )

            call_args = mock_instance.post.call_args
            headers = call_args[1]["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_execute_signal_includes_request_id(self, client):
        """Should include X-Request-ID header when provided."""
        portfolio = PortfolioState(position=0.0, cash=100000.0, initial_capital=100000.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = {
                "action": "hold", "size": 0.0, "value": 0.0,
                "reason": "", "available_cash": 100000.0,
                "position_after": 0.0, "stopped": False}
            mock_response.raise_for_status = Mock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await client.execute_signal(
                forecast_price=450.0,
                current_price=450.0,
                portfolio=portfolio,
                request_id="test-request-123",
            )

            call_args = mock_instance.post.call_args
            headers = call_args[1]["headers"]
            assert "X-Request-ID" in headers
            assert headers["X-Request-ID"] == "test-request-123"


class TestRequestIDPropagation:
    """Tests for request ID propagation across clients."""

    @pytest.mark.asyncio
    async def test_metrics_client_propagates_request_id(self):
        """MetricsClient should propagate X-Request-ID header."""
        client = MetricsClient(base_url="http://test:8000", timeout=5.0)

        mock_response = Mock()
        mock_response.json.return_value = {
            "sharpe_ratio": 1.0, "max_drawdown": 0.1,
            "cagr": 0.2, "calmar_ratio": 2.0, "win_rate": 0.6
        }
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await client.compute_metrics(
                returns=[0.01, 0.02, -0.01, 0.03],
                request_id="metrics-req-456",
            )

            call_args = mock_instance.post.call_args
            headers = call_args[1]["headers"]
            assert "X-Request-ID" in headers
            assert headers["X-Request-ID"] == "metrics-req-456"

    @pytest.mark.asyncio
    async def test_data_client_propagates_request_id_on_query(self):
        """DataClient.query_data should propagate X-Request-ID header."""
        from orchestration.clients.data_client import DataClient

        client = DataClient(base_url="http://test:8000", timeout=5.0)

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [{"close": 100.0}, {"close": 101.0}]
        }
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await client.query_data(
                ticker="SPY",
                days=90,
                request_id="data-query-789",
            )

            call_args = mock_instance.post.call_args
            headers = call_args[1]["headers"]
            assert "X-Request-ID" in headers
            assert headers["X-Request-ID"] == "data-query-789"

    @pytest.mark.asyncio
    async def test_data_client_propagates_request_id_on_write(self):
        """DataClient.write_results should propagate X-Request-ID header."""
        from orchestration.clients.data_client import DataClient, ResultPoint, MetricsSummary

        client = DataClient(base_url="http://test:8000", timeout=5.0)

        mock_response = Mock()
        mock_response.json.return_value = {"points_written": 1}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await client.write_results(
                run_id="test-run",
                ticker="SPY",
                model="chronos",
                strategy="threshold",
                results=[ResultPoint(
                    date="2025-01-01", forecast=100.0, actual=101.0,
                    signal="buy", position=10.0, cash=9000.0, portfolio_value=10000.0
                )],
                metrics=MetricsSummary(
                    sharpe_ratio=1.0, max_drawdown=0.1,
                    cagr=0.2, calmar_ratio=2.0, win_rate=0.6
                ),
                request_id="write-results-abc",
            )

            call_args = mock_instance.post.call_args
            headers = call_args[1]["headers"]
            assert "X-Request-ID" in headers
            assert headers["X-Request-ID"] == "write-results-abc"

    def test_trading_client_build_headers_with_request_id(self):
        """TradingClient._build_headers should include X-Request-ID."""
        client = TradingClient(api_key="test-key")
        headers = client._build_headers(request_id="req-123")

        assert headers["X-Request-ID"] == "req-123"
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"

    def test_trading_client_build_headers_without_request_id(self):
        """TradingClient._build_headers should omit X-Request-ID if None."""
        client = TradingClient(api_key="test-key")
        headers = client._build_headers(request_id=None)

        assert "X-Request-ID" not in headers
        assert "Authorization" in headers

    def test_metrics_client_build_headers_with_request_id(self):
        """MetricsClient._build_headers should include X-Request-ID."""
        client = MetricsClient()
        headers = client._build_headers(request_id="metrics-123")

        assert headers["X-Request-ID"] == "metrics-123"
        assert headers["Content-Type"] == "application/json"
