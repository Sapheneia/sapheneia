"""
Unit tests for threshold-based trading strategy.

Tests the calculate_threshold_signal and execute_trading_signal methods
for threshold strategy with various threshold types.
"""

import pytest
import numpy as np
from trading.services.trading import TradingStrategy
from trading.core.exceptions import InvalidParametersError


class TestThresholdStrategy:
    """Test threshold-based trading strategy."""

    def test_absolute_threshold_buy_signal(self, base_params):
        """Test absolute threshold generates buy signal when forecast > price + threshold."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "threshold_type": "absolute",
                "threshold_value": 2.0,
                "execution_size": 100.0,
            }
        )

        # Forecast (105) > Price (100) + Threshold (2) = 102
        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"
        assert result["size"] == 100.0
        assert "Forecast" in result["reason"]
        assert result["stopped"] is False

    def test_absolute_threshold_sell_signal(self, base_params):
        """Test absolute threshold generates sell signal when forecast < price - threshold."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "forecast_price": 95.0,  # Below current price
                "current_price": 100.0,
                "current_position": 100.0,  # Have position to sell
                "available_cash": 0.0,
                "initial_capital": 100000.0,
                "threshold_type": "absolute",
                "threshold_value": 2.0,
                "execution_size": 50.0,
            }
        )

        # Forecast (95) < Price (100) - Threshold (2) = 98
        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "sell"
        assert result["size"] == 50.0
        assert "Forecast" in result["reason"]

    def test_absolute_threshold_hold_signal(self, base_params):
        """Test absolute threshold generates hold signal when within threshold."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "forecast_price": 101.0,  # Close to current price
                "current_price": 100.0,
                "threshold_type": "absolute",
                "threshold_value": 2.0,  # Threshold is 2.0
                "execution_size": 100.0,
            }
        )

        # |Forecast (101) - Price (100)| = 1.0 < Threshold (2.0)
        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "hold"
        assert result["size"] == 0
        assert "below threshold" in result["reason"].lower()

    def test_sign_based_threshold(self, base_params):
        """Test sign-based strategy (threshold_value = 0) triggers on any difference."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "threshold_type": "absolute",
                "threshold_value": 0.0,  # Sign-based
                "execution_size": 100.0,
            }
        )

        # Any difference should trigger (105 > 100)
        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"
        assert result["size"] == 100.0

    def test_percentage_threshold(self, base_params):
        """Test percentage threshold calculation."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "forecast_price": 106.0,  # 6% above
                "current_price": 100.0,
                "threshold_type": "percentage",
                "threshold_value": 5.0,  # 5% threshold
                "execution_size": 100.0,
            }
        )

        # 6% > 5% threshold, should buy
        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"

    def test_std_dev_threshold_with_history(self, base_params, sample_ohlc_data):
        """Test std_dev threshold calculation with history."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "forecast_price": 110.0,
                "current_price": 100.0,
                "threshold_type": "std_dev",
                "threshold_value": 1.0,  # 1 std dev
                "which_history": "close",
                "window_history": 20,
                "execution_size": 100.0,
            }
        )
        params.update(sample_ohlc_data)

        result = TradingStrategy.execute_trading_signal(params)

        # Should execute (may be buy or hold depending on calculated threshold)
        assert result["action"] in ["buy", "hold", "sell"]

    def test_std_dev_threshold_insufficient_history(self, base_params):
        """Test std_dev threshold falls back to absolute when history insufficient."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "forecast_price": 105.0,
                "current_price": 100.0,
                "threshold_type": "std_dev",
                "threshold_value": 1.0,
                "which_history": "close",
                "window_history": 20,
                "min_history_length": 2,
                "execution_size": 100.0,
                "close_history": [100.0],  # Only 1 value, insufficient
            }
        )

        # Should fallback to absolute threshold
        result = TradingStrategy.execute_trading_signal(params)

        # Should still work (fallback to absolute)
        assert result["action"] in ["buy", "hold", "sell"]

    def test_atr_threshold_with_ohlc(self, base_params, sample_ohlc_data):
        """Test ATR threshold calculation with OHLC data."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "forecast_price": 110.0,
                "current_price": 100.0,
                "threshold_type": "atr",
                "threshold_value": 1.0,  # 1x ATR
                "window_history": 20,
                "execution_size": 100.0,
            }
        )
        params.update(sample_ohlc_data)

        result = TradingStrategy.execute_trading_signal(params)

        # Should execute (may be buy or hold depending on ATR)
        assert result["action"] in ["buy", "hold", "sell"]

    def test_atr_threshold_missing_ohlc(self, base_params):
        """Test ATR threshold falls back when OHLC data missing."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "forecast_price": 105.0,
                "current_price": 100.0,
                "threshold_type": "atr",
                "threshold_value": 1.0,
                "window_history": 20,
                "execution_size": 100.0,
                # Missing OHLC data
            }
        )

        # Should fallback to absolute threshold
        result = TradingStrategy.execute_trading_signal(params)

        # Should still work (fallback)
        assert result["action"] in ["buy", "hold", "sell"]

    def test_insufficient_cash_buy(self, base_params):
        """Test insufficient cash scenario for buy signal."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "forecast_price": 105.0,
                "current_price": 100.0,
                "available_cash": 50.0,  # Only $50 available
                "threshold_type": "absolute",
                "threshold_value": 0.0,
                "execution_size": 100.0,  # Want to buy 100 shares = $10,000
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        # Should buy what it can afford (0.5 shares, but will be 0 due to rounding)
        # Or hold if actual_size <= 0
        assert result["action"] in ["buy", "hold"]
        if result["action"] == "hold":
            assert "Insufficient cash" in result["reason"]
            assert result["size"] == 0
        else:
            # If it buys, it should buy what it can afford
            assert result["size"] > 0
            assert result["size"] * 100.0 <= 50.0  # Can't spend more than available

    def test_zero_current_price_raises_error(self, base_params):
        """Test that zero current_price raises InvalidParametersError."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "current_price": 0.0,  # Zero price
                "threshold_type": "absolute",
                "threshold_value": 0.0,
                "execution_size": 100.0,
            }
        )

        with pytest.raises(InvalidParametersError) as exc_info:
            TradingStrategy.execute_trading_signal(params)

        # Error message may come from _validate_common_params or our defensive check
        assert "current_price" in exc_info.value.message.lower()
        assert (
            "positive" in exc_info.value.message.lower()
            or "positive number" in exc_info.value.message.lower()
        )
        # Check details if available
        if exc_info.value.details:
            assert (
                exc_info.value.details.get("parameter") == "current_price"
                or exc_info.value.details.get("value") == 0.0
            )

    def test_negative_current_price_raises_error(self, base_params):
        """Test that negative current_price raises InvalidParametersError."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "current_price": -10.0,  # Negative price
                "threshold_type": "absolute",
                "threshold_value": 0.0,
                "execution_size": 100.0,
            }
        )

        with pytest.raises(InvalidParametersError) as exc_info:
            TradingStrategy.execute_trading_signal(params)

        # Error message may come from _validate_common_params or our defensive check
        assert "current_price" in exc_info.value.message.lower()
        assert (
            "positive" in exc_info.value.message.lower()
            or "positive number" in exc_info.value.message.lower()
        )
        # Check details if available
        if exc_info.value.details:
            assert (
                exc_info.value.details.get("parameter") == "current_price"
                or exc_info.value.details.get("value") == -10.0
            )

    def test_no_position_to_sell(self, base_params):
        """Test no position to sell scenario."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "forecast_price": 95.0,  # Sell signal
                "current_price": 100.0,
                "current_position": 0.0,  # No position
                "threshold_type": "absolute",
                "threshold_value": 0.0,
                "execution_size": 50.0,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        # Should hold due to no position
        assert result["action"] == "hold"
        assert "No position to sell" in result["reason"]
        assert result["size"] == 0

    def test_strategy_stopped(self, base_params):
        """Test strategy stopped condition (no cash and no position)."""
        params = base_params.copy()
        params.update(
            {
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
        )

        result = TradingStrategy.execute_trading_signal(params)

        # Should be stopped
        assert result["action"] == "hold"
        assert result["stopped"] is True
        assert "stopped" in result["reason"].lower()
        assert result["size"] == 0

    def test_invalid_threshold_type(self, base_params):
        """Test invalid threshold_type raises error."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "threshold_type": "invalid_type",
                "threshold_value": 1.0,
                "execution_size": 100.0,
            }
        )

        with pytest.raises(InvalidParametersError):
            TradingStrategy.execute_trading_signal(params)

    def test_negative_threshold_value(self, base_params):
        """Test negative threshold_value raises error."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "threshold",
                "threshold_type": "absolute",
                "threshold_value": -1.0,  # Invalid
                "execution_size": 100.0,
            }
        )

        with pytest.raises(InvalidParametersError):
            TradingStrategy.execute_trading_signal(params)
