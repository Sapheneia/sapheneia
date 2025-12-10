"""
Unit tests for TradingStrategy helper methods.

Tests utility methods like ATR calculation, returns calculation,
threshold calculation, history array getters, and portfolio utilities.
"""

import pytest
import numpy as np
from trading.services.trading import TradingStrategy


class TestATRCalculation:
    """Test Average True Range (ATR) calculation."""

    def test_calculate_atr_valid_data(self):
        """Test ATR calculation with valid OHLC data."""
        open_history = np.array([100.0, 101.0, 102.0, 103.0, 104.0])
        high_history = np.array([105.0, 106.0, 107.0, 108.0, 109.0])
        low_history = np.array([95.0, 96.0, 97.0, 98.0, 99.0])
        close_history = np.array([102.0, 103.0, 104.0, 105.0, 106.0])

        atr = TradingStrategy._calculate_atr(
            open_history,
            high_history,
            low_history,
            close_history,
            window_history=5,
            min_history_length=2,
        )

        assert atr > 0
        assert isinstance(atr, float)

    def test_calculate_atr_insufficient_data(self):
        """Test ATR returns 0.0 when data is insufficient."""
        open_history = np.array([100.0])
        high_history = np.array([105.0])
        low_history = np.array([95.0])
        close_history = np.array([102.0])

        atr = TradingStrategy._calculate_atr(
            open_history,
            high_history,
            low_history,
            close_history,
            window_history=5,
            min_history_length=2,
        )

        assert atr == 0.0

    def test_calculate_atr_single_period(self):
        """Test ATR with only one period of data."""
        open_history = np.array([100.0, 101.0])
        high_history = np.array([105.0, 106.0])
        low_history = np.array([95.0, 96.0])
        close_history = np.array([102.0, 103.0])

        atr = TradingStrategy._calculate_atr(
            open_history,
            high_history,
            low_history,
            close_history,
            window_history=2,
            min_history_length=2,
        )

        # Should calculate TR for period 1 (needs prev_close from period 0)
        # With only 2 periods, we get 1 TR value
        assert atr >= 0


class TestReturnsCalculation:
    """Test returns calculation."""

    def test_calculate_returns_valid_series(self):
        """Test returns calculation with valid time series."""
        timeseries = np.array([100.0, 105.0, 110.0, 115.0, 120.0])
        returns = TradingStrategy._calculate_returns(timeseries)

        assert len(returns) == len(timeseries) - 1
        assert all(returns > 0)  # All positive returns
        # First return: (105 - 100) / 100 = 0.05
        assert returns[0] == pytest.approx(0.05, rel=0.01)

    def test_calculate_returns_empty_series(self):
        """Test returns with empty series."""
        timeseries = np.array([])
        returns = TradingStrategy._calculate_returns(timeseries)

        assert len(returns) == 0

    def test_calculate_returns_single_value(self):
        """Test returns with single value."""
        timeseries = np.array([100.0])
        returns = TradingStrategy._calculate_returns(timeseries)

        assert len(returns) == 0

    def test_calculate_returns_negative_returns(self):
        """Test returns calculation with negative returns."""
        timeseries = np.array([100.0, 95.0, 90.0, 85.0])
        returns = TradingStrategy._calculate_returns(timeseries)

        assert len(returns) == 3
        assert all(returns < 0)  # All negative returns

    def test_calculate_returns_zero_value_raises_error(self):
        """Test that zero values in timeseries raise InvalidParametersError."""
        from trading.core.exceptions import InvalidParametersError

        timeseries = np.array([100.0, 0.0, 110.0])

        with pytest.raises(InvalidParametersError) as exc_info:
            TradingStrategy._calculate_returns(timeseries)

        assert "zero or negative values" in exc_info.value.message.lower()
        # Check details dict for parameter name
        if exc_info.value.details and "parameter" in exc_info.value.details:
            assert "timeseries" in exc_info.value.details["parameter"].lower()
        else:
            # Parameter may be in message or details
            assert "timeseries" in str(exc_info.value).lower()

    def test_calculate_returns_negative_value_raises_error(self):
        """Test that negative values in timeseries raise InvalidParametersError."""
        from trading.core.exceptions import InvalidParametersError

        timeseries = np.array([100.0, -5.0, 110.0])

        with pytest.raises(InvalidParametersError) as exc_info:
            TradingStrategy._calculate_returns(timeseries)

        assert "zero or negative values" in exc_info.value.message.lower()
        # Check details dict for parameter name
        if exc_info.value.details and "parameter" in exc_info.value.details:
            assert "timeseries" in exc_info.value.details["parameter"].lower()
        else:
            # Parameter may be in message or details
            assert "timeseries" in str(exc_info.value).lower()


class TestThresholdCalculation:
    """Test threshold calculation for different types."""

    def test_calculate_threshold_absolute(self):
        """Test absolute threshold calculation."""
        threshold = TradingStrategy._calculate_threshold(
            threshold_type="absolute",
            threshold_value=5.0,
            open_history=None,
            high_history=None,
            low_history=None,
            close_history=None,
            which_history="close",
            window_history=20,
            min_history_length=2,
            current_price=100.0,
        )

        assert threshold == 5.0

    def test_calculate_threshold_percentage(self):
        """Test percentage threshold calculation."""
        threshold = TradingStrategy._calculate_threshold(
            threshold_type="percentage",
            threshold_value=5.0,  # 5%
            open_history=None,
            high_history=None,
            low_history=None,
            close_history=None,
            which_history="close",
            window_history=20,
            min_history_length=2,
            current_price=100.0,
        )

        # 5% of 100 = 5.0
        assert threshold == pytest.approx(5.0, rel=0.01)

    def test_calculate_threshold_std_dev(self):
        """Test std_dev threshold calculation."""
        close_history = np.array(
            [
                95.0,
                96.0,
                97.0,
                98.0,
                99.0,
                100.0,
                101.0,
                102.0,
                103.0,
                104.0,
                105.0,
                106.0,
                107.0,
                108.0,
                109.0,
                110.0,
                111.0,
                112.0,
                113.0,
                114.0,
            ]
        )

        threshold = TradingStrategy._calculate_threshold(
            threshold_type="std_dev",
            threshold_value=2.0,  # 2 std devs
            open_history=None,
            high_history=None,
            low_history=None,
            close_history=close_history,
            which_history="close",
            window_history=20,
            min_history_length=2,
            current_price=100.0,
        )

        # Should be 2.0 * std(close_history)
        assert threshold > 0
        std_dev = np.std(close_history)
        expected = 2.0 * std_dev
        assert threshold == pytest.approx(expected, rel=0.01)

    def test_calculate_threshold_atr(self):
        """Test ATR threshold calculation."""
        open_history = np.array([100.0] * 20)
        high_history = np.array([110.0] * 20)
        low_history = np.array([90.0] * 20)
        close_history = np.array([100.0] * 20)

        threshold = TradingStrategy._calculate_threshold(
            threshold_type="atr",
            threshold_value=1.5,  # 1.5x ATR
            open_history=open_history,
            high_history=high_history,
            low_history=low_history,
            close_history=close_history,
            which_history="close",
            window_history=20,
            min_history_length=2,
            current_price=100.0,
        )

        # Should be 1.5 * ATR
        assert threshold > 0


class TestHistoryArrayGetter:
    """Test history array getter method."""

    def test_get_history_array_open(self, sample_ohlc_data):
        """Test getting open history."""
        history = TradingStrategy._get_history_array(sample_ohlc_data, "open")

        assert history is not None
        assert len(history) == len(sample_ohlc_data["open_history"])

    def test_get_history_array_high(self, sample_ohlc_data):
        """Test getting high history."""
        history = TradingStrategy._get_history_array(sample_ohlc_data, "high")

        assert history is not None
        assert len(history) == len(sample_ohlc_data["high_history"])

    def test_get_history_array_low(self, sample_ohlc_data):
        """Test getting low history."""
        history = TradingStrategy._get_history_array(sample_ohlc_data, "low")

        assert history is not None
        assert len(history) == len(sample_ohlc_data["low_history"])

    def test_get_history_array_close(self, sample_ohlc_data):
        """Test getting close history."""
        history = TradingStrategy._get_history_array(sample_ohlc_data, "close")

        assert history is not None
        assert len(history) == len(sample_ohlc_data["close_history"])

    def test_get_history_array_default_close(self):
        """Test default to close when history type not found."""
        params = {"close_history": [100.0, 101.0, 102.0]}

        history = TradingStrategy._get_history_array(params, "invalid")

        # Should default to close
        assert history is not None
        assert len(history) == 3


class TestPortfolioUtilities:
    """Test portfolio value and return calculations."""

    def test_get_portfolio_value(self):
        """Test portfolio value calculation."""
        current_position = 100.0
        current_price = 100.0
        available_cash = 50000.0

        portfolio_value = TradingStrategy.get_portfolio_value(
            current_position, current_price, available_cash
        )

        # Position value: 100 * 100 = 10,000
        # Total: 10,000 + 50,000 = 60,000
        assert portfolio_value == pytest.approx(60000.0, rel=0.01)

    def test_get_portfolio_return_positive(self):
        """Test portfolio return calculation with positive return."""
        current_position = 100.0
        current_price = 110.0  # Price increased
        available_cash = 0.0
        initial_capital = 10000.0

        # Position value: 100 * 110 = 11,000
        # Return: (11,000 - 10,000) / 10,000 = 0.10 (10%)
        portfolio_return = TradingStrategy.get_portfolio_return(
            current_position, current_price, available_cash, initial_capital
        )

        assert portfolio_return == pytest.approx(0.10, rel=0.01)

    def test_get_portfolio_return_negative(self):
        """Test portfolio return calculation with negative return."""
        current_position = 100.0
        current_price = 90.0  # Price decreased
        available_cash = 0.0
        initial_capital = 10000.0

        # Position value: 100 * 90 = 9,000
        # Return: (9,000 - 10,000) / 10,000 = -0.10 (-10%)
        portfolio_return = TradingStrategy.get_portfolio_return(
            current_position, current_price, available_cash, initial_capital
        )

        assert portfolio_return == pytest.approx(-0.10, rel=0.01)

    def test_get_portfolio_return_zero_initial_capital(self):
        """Test portfolio return with zero initial capital returns 0.0."""
        current_position = 100.0
        current_price = 100.0
        available_cash = 0.0
        initial_capital = 0.0

        portfolio_return = TradingStrategy.get_portfolio_return(
            current_position, current_price, available_cash, initial_capital
        )

        assert portfolio_return == 0.0

    def test_get_portfolio_return_with_cash(self):
        """Test portfolio return includes cash in calculation."""
        current_position = 50.0
        current_price = 100.0
        available_cash = 5000.0
        initial_capital = 10000.0

        # Position value: 50 * 100 = 5,000
        # Total value: 5,000 + 5,000 = 10,000
        # Return: (10,000 - 10,000) / 10,000 = 0.0
        portfolio_return = TradingStrategy.get_portfolio_return(
            current_position, current_price, available_cash, initial_capital
        )

        assert portfolio_return == pytest.approx(0.0, rel=0.01)
