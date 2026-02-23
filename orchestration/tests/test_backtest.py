"""
Tests for orchestration/backtest.py

Tests the backtest orchestrator: date generation, result properties,
and the main run_backtest loop with fully mocked dependencies.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

from orchestration.backtest import (
    generate_evaluation_dates,
    calculate_start_date,
    BacktestConfig,
    BacktestResult,
    run_backtest,
)
from orchestration.adapters import DateParseError
from orchestration.clients.trading_client import (
    TradeAction,
    TradeResult,
    StrategyType,
    PortfolioState,
)
from orchestration.clients.metrics_client import MetricsResponse


# =============================================================================
# generate_evaluation_dates
# =============================================================================

class TestGenerateEvaluationDates:
    """Tests for generate_evaluation_dates function."""

    def test_basic_range(self):
        """Should generate dates for a simple weekday range."""
        dates = generate_evaluation_dates("2025-01-06", "2025-01-10")
        # Mon-Fri of that week
        assert dates == [
            "2025-01-06", "2025-01-07", "2025-01-08",
            "2025-01-09", "2025-01-10",
        ]

    def test_skips_weekends(self):
        """Weekends should be excluded."""
        # Fri to Mon
        dates = generate_evaluation_dates("2025-01-10", "2025-01-13")
        assert "2025-01-11" not in dates  # Saturday
        assert "2025-01-12" not in dates  # Sunday
        assert "2025-01-10" in dates      # Friday
        assert "2025-01-13" in dates      # Monday

    def test_step_days(self):
        """step_days should control interval between evaluations."""
        dates = generate_evaluation_dates("2025-01-06", "2025-01-17", step_days=3)
        # Jan 6 (Mon), Jan 9 (Thu), Jan 12 (Sun - skipped), Jan 15 (Wed)
        assert "2025-01-06" in dates
        assert "2025-01-09" in dates
        assert "2025-01-12" not in dates  # Sunday
        assert "2025-01-15" in dates

    def test_start_after_end_raises(self):
        """start > end should raise ValueError."""
        with pytest.raises(ValueError, match="must be before"):
            generate_evaluation_dates("2025-12-30", "2025-01-01")

    def test_same_start_end(self):
        """Same start and end should return single date if weekday."""
        dates = generate_evaluation_dates("2025-01-06", "2025-01-06")
        assert dates == ["2025-01-06"]

    def test_same_start_end_weekend(self):
        """Same start and end on weekend should return empty list."""
        dates = generate_evaluation_dates("2025-01-11", "2025-01-11")
        assert dates == []

    def test_invalid_date_raises(self):
        """Invalid date strings should raise DateParseError."""
        with pytest.raises(DateParseError):
            generate_evaluation_dates("not-a-date", "2025-01-10")

    def test_yyyymmdd_format(self):
        """Should accept YYYYMMDD format."""
        dates = generate_evaluation_dates("20250106", "20250110")
        assert len(dates) == 5


# =============================================================================
# calculate_start_date
# =============================================================================

class TestCalculateStartDate:
    """Tests for calculate_start_date function."""

    def test_basic_subtraction(self):
        """Should subtract correct number of days."""
        result = calculate_start_date("2025-01-15", 10)
        assert result == "2025-01-05"

    def test_crosses_month_boundary(self):
        """Should handle month boundary correctly."""
        result = calculate_start_date("2025-02-05", 10)
        assert result == "2025-01-26"

    def test_invalid_date_raises(self):
        """Invalid date should raise DateParseError."""
        with pytest.raises(DateParseError):
            calculate_start_date("bad-date", 10)


# =============================================================================
# BacktestResult Properties
# =============================================================================

class TestBacktestResult:
    """Tests for BacktestResult dataclass properties."""

    def _make_config(self):
        return BacktestConfig(
            ticker="SPY",
            model="amazon/chronos-t5-tiny",
            start_date="2025-01-01",
            end_date="2025-01-31",
        )

    def _make_metrics(self):
        return MetricsResponse(
            sharpe_ratio=1.5,
            max_drawdown=-0.10,
            cagr=0.20,
            calmar_ratio=2.0,
            win_rate=0.55,
        )

    def test_total_return(self):
        """total_return should calculate (final - initial) / initial."""
        result = BacktestResult(
            config=self._make_config(),
            trades=[],
            equity_curve=[100000.0, 105000.0, 110000.0],
            metrics=self._make_metrics(),
            evaluation_dates=["2025-01-06"],
        )
        assert result.total_return == pytest.approx(0.10)

    def test_total_return_empty_curve(self):
        """total_return with < 2 points should return 0."""
        result = BacktestResult(
            config=self._make_config(),
            trades=[],
            equity_curve=[100000.0],
            metrics=self._make_metrics(),
            evaluation_dates=[],
        )
        assert result.total_return == 0.0

    def test_final_value(self):
        """final_value should return last equity curve entry."""
        result = BacktestResult(
            config=self._make_config(),
            trades=[],
            equity_curve=[100000.0, 95000.0, 110000.0],
            metrics=self._make_metrics(),
            evaluation_dates=[],
        )
        assert result.final_value == 110000.0

    def test_final_value_empty_curve(self):
        """final_value with empty curve should return 0."""
        result = BacktestResult(
            config=self._make_config(),
            trades=[],
            equity_curve=[],
            metrics=self._make_metrics(),
            evaluation_dates=[],
        )
        assert result.final_value == 0.0

    def test_to_dict_includes_error_fields(self):
        """to_dict should include error_count and failed_dates."""
        result = BacktestResult(
            config=self._make_config(),
            trades=[],
            equity_curve=[100000.0, 105000.0],
            metrics=self._make_metrics(),
            evaluation_dates=["2025-01-06", "2025-01-07"],
            error_count=1,
            failed_dates=["2025-01-07"],
        )
        d = result.to_dict()
        assert d["error_count"] == 1
        assert d["failed_dates"] == ["2025-01-07"]
        assert d["total_return"] == pytest.approx(0.05)
        assert d["final_value"] == 105000.0


# =============================================================================
# run_backtest (fully mocked)
# =============================================================================

def _make_trade_result(action=TradeAction.HOLD, cash=100000.0, position=0.0):
    """Helper to create a TradeResult."""
    return TradeResult(
        action=action,
        size=0.0,
        value=0.0,
        reason="test",
        available_cash=cash,
        position_after=position,
        stopped=False,
    )


class TestRunBacktest:
    """Tests for run_backtest with mocked dependencies."""

    @pytest.fixture
    def config(self):
        return BacktestConfig(
            ticker="SPY",
            model="amazon/chronos-t5-tiny",
            start_date="2025-01-06",
            end_date="2025-01-08",
            initial_capital=100000.0,
            context_size=90,
            horizon_size=10,
        )

    @pytest.fixture
    def mock_data_provider(self):
        """Data provider returning 90 prices."""
        provider = AsyncMock()
        provider.return_value = [450.0 + i * 0.1 for i in range(90)]
        return provider

    @pytest.fixture
    def mock_inference_response(self):
        """Mock InferenceResponse with forecast values."""
        resp = Mock()
        resp.forecast = Mock()
        resp.forecast.values = [455.0, 456.0, 457.0, 458.0, 459.0]
        return resp

    @pytest.mark.asyncio
    async def test_happy_path(self, config, mock_data_provider, mock_inference_response):
        """Full backtest loop should produce a valid result."""
        trade = _make_trade_result(TradeAction.BUY, cash=95000.0, position=10.0)

        with patch("orchestration.backtest.InferenceService") as MockIS, \
             patch("orchestration.backtest.TradingClient") as MockTC, \
             patch("orchestration.backtest.MetricsClient") as MockMC:

            MockIS.return_value.predict = AsyncMock(return_value=mock_inference_response)
            MockTC.return_value.execute_signal = AsyncMock(return_value=trade)
            MockMC.return_value.compute_metrics = AsyncMock(
                return_value=MetricsResponse(1.0, -0.05, 0.15, 1.5, 0.55)
            )

            result = await run_backtest(config, mock_data_provider, run_id="test-1")

            assert result.run_id == "test-1"
            assert len(result.trades) == 3  # Jan 6, 7, 8 (3 weekdays)
            assert result.error_count == 0
            assert result.failed_dates == []
            assert result.metrics.sharpe_ratio == 1.0

    @pytest.mark.asyncio
    async def test_empty_data_skips_date(self, config, mock_inference_response):
        """When data_provider returns empty list, date should be skipped."""
        data_provider = AsyncMock(return_value=[])

        with patch("orchestration.backtest.InferenceService") as MockIS, \
             patch("orchestration.backtest.TradingClient") as MockTC, \
             patch("orchestration.backtest.MetricsClient") as MockMC:

            MockIS.return_value.predict = AsyncMock(return_value=mock_inference_response)
            MockTC.return_value.execute_signal = AsyncMock()
            MockMC.return_value.compute_metrics = AsyncMock(
                return_value=MetricsResponse(0.0, 0.0, 0.0, 0.0, 0.0)
            )

            result = await run_backtest(config, data_provider)

            # No trades should have been executed
            assert len(result.trades) == 0
            # Inference should not have been called
            MockIS.return_value.predict.assert_not_called()

    @pytest.mark.asyncio
    async def test_insufficient_data_skips_date(self, config, mock_inference_response):
        """When data_provider returns < 10 points, date should be skipped."""
        data_provider = AsyncMock(return_value=[100.0, 101.0, 102.0])

        with patch("orchestration.backtest.InferenceService") as MockIS, \
             patch("orchestration.backtest.TradingClient") as MockTC, \
             patch("orchestration.backtest.MetricsClient") as MockMC:

            MockIS.return_value.predict = AsyncMock()
            MockTC.return_value.execute_signal = AsyncMock()
            MockMC.return_value.compute_metrics = AsyncMock(
                return_value=MetricsResponse(0.0, 0.0, 0.0, 0.0, 0.0)
            )

            result = await run_backtest(config, data_provider)
            assert len(result.trades) == 0

    @pytest.mark.asyncio
    async def test_inference_failure_increments_error_count(self, config, mock_data_provider):
        """When inference fails on a date, error_count should increase."""
        with patch("orchestration.backtest.InferenceService") as MockIS, \
             patch("orchestration.backtest.TradingClient") as MockTC, \
             patch("orchestration.backtest.MetricsClient") as MockMC:

            MockIS.return_value.predict = AsyncMock(side_effect=RuntimeError("model failed"))
            MockTC.return_value.execute_signal = AsyncMock()
            MockMC.return_value.compute_metrics = AsyncMock(
                return_value=MetricsResponse(0.0, 0.0, 0.0, 0.0, 0.0)
            )

            result = await run_backtest(config, mock_data_provider)

            # All 3 dates (Jan 6, 7, 8) should have failed
            assert result.error_count == 3
            assert len(result.failed_dates) == 3

    @pytest.mark.asyncio
    async def test_partial_failure_continues(self, config, mock_inference_response):
        """Backtest should continue after individual date failures."""
        call_count = 0

        async def mixed_data_provider(ticker, date, days):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ConnectionError("network issue")
            return [450.0 + i for i in range(90)]

        trade = _make_trade_result()

        with patch("orchestration.backtest.InferenceService") as MockIS, \
             patch("orchestration.backtest.TradingClient") as MockTC, \
             patch("orchestration.backtest.MetricsClient") as MockMC:

            MockIS.return_value.predict = AsyncMock(return_value=mock_inference_response)
            MockTC.return_value.execute_signal = AsyncMock(return_value=trade)
            MockMC.return_value.compute_metrics = AsyncMock(
                return_value=MetricsResponse(0.0, 0.0, 0.0, 0.0, 0.0)
            )

            result = await run_backtest(config, mixed_data_provider)

            # 1 error, but other dates should have succeeded
            assert result.error_count == 1
            assert len(result.trades) == 2  # 3 dates - 1 failure

    @pytest.mark.asyncio
    async def test_metrics_failure_uses_fallback(self, config, mock_data_provider, mock_inference_response):
        """When post-loop metrics fail, fallback zeros should be used."""
        trade = _make_trade_result()

        with patch("orchestration.backtest.InferenceService") as MockIS, \
             patch("orchestration.backtest.TradingClient") as MockTC, \
             patch("orchestration.backtest.MetricsClient") as MockMC:

            MockIS.return_value.predict = AsyncMock(return_value=mock_inference_response)
            MockTC.return_value.execute_signal = AsyncMock(return_value=trade)
            MockMC.return_value.compute_metrics = AsyncMock(
                side_effect=RuntimeError("metrics service down")
            )
            MockMC.return_value._get_fallback_metrics = Mock(
                return_value=MetricsResponse(0.0, 0.0, 0.0, 0.0, 0.0)
            )

            result = await run_backtest(config, mock_data_provider)

            # Trades should still be recorded
            assert len(result.trades) > 0
            # Metrics should be fallback zeros
            assert result.metrics.sharpe_ratio == 0.0

    @pytest.mark.asyncio
    async def test_checkpoint_callback_invoked(self, config, mock_data_provider, mock_inference_response):
        """Checkpoint callback should be invoked at interval."""
        # Use a longer date range so we hit checkpoint_interval (default=10)
        config.start_date = "2025-01-06"
        config.end_date = "2025-01-31"

        trade = _make_trade_result()
        callback = Mock()

        with patch("orchestration.backtest.InferenceService") as MockIS, \
             patch("orchestration.backtest.TradingClient") as MockTC, \
             patch("orchestration.backtest.MetricsClient") as MockMC:

            MockIS.return_value.predict = AsyncMock(return_value=mock_inference_response)
            MockTC.return_value.execute_signal = AsyncMock(return_value=trade)
            MockMC.return_value.compute_metrics = AsyncMock(
                return_value=MetricsResponse(0.0, 0.0, 0.0, 0.0, 0.0)
            )

            result = await run_backtest(
                config, mock_data_provider,
                checkpoint_callback=callback,
            )

            # 20 weekdays in Jan 6-31 range, checkpoint_interval=10 → 2 checkpoints
            assert callback.call_count == 2

    @pytest.mark.asyncio
    async def test_run_id_auto_generated(self, config, mock_data_provider, mock_inference_response):
        """run_id should be auto-generated if not provided."""
        trade = _make_trade_result()

        with patch("orchestration.backtest.InferenceService") as MockIS, \
             patch("orchestration.backtest.TradingClient") as MockTC, \
             patch("orchestration.backtest.MetricsClient") as MockMC:

            MockIS.return_value.predict = AsyncMock(return_value=mock_inference_response)
            MockTC.return_value.execute_signal = AsyncMock(return_value=trade)
            MockMC.return_value.compute_metrics = AsyncMock(
                return_value=MetricsResponse(0.0, 0.0, 0.0, 0.0, 0.0)
            )

            result = await run_backtest(config, mock_data_provider)

            assert result.run_id != ""
            assert len(result.run_id) == 8
