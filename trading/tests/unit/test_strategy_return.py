"""
Unit tests for return-based trading strategy.

Tests the calculate_return_signal and execute_trading_signal methods
for return strategy with various position sizing methods.
"""

import pytest
import numpy as np
from trading.services.trading import TradingStrategy
from trading.core.exceptions import InvalidParametersError


class TestReturnStrategy:
    """Test return-based trading strategy."""

    def test_fixed_position_sizing_buy(self, base_params):
        """Test fixed position sizing for buy signal."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 110.0,  # 10% return
                "current_price": 100.0,
                "position_sizing": "fixed",
                "threshold_value": 0.05,  # 5% threshold
                "execution_size": 10.0,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"
        assert result["size"] == 10.0  # Fixed size
        assert "Expected return" in result["reason"]

    def test_fixed_position_sizing_sell(self, base_params):
        """Test fixed position sizing for sell signal."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 90.0,  # -10% return
                "current_price": 100.0,
                "current_position": 100.0,
                "position_sizing": "fixed",
                "threshold_value": 0.05,  # 5% threshold
                "execution_size": 10.0,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "sell"
        assert result["size"] == 10.0  # Fixed size

    def test_proportional_position_sizing(self, base_params):
        """Test proportional position sizing scales with return magnitude."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 110.0,  # 10% return
                "current_price": 100.0,
                "position_sizing": "proportional",
                "threshold_value": 0.05,
                "execution_size": 10.0,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"
        # Proportional: execution_size * abs(return) * 100
        # = 10.0 * 0.10 * 100 = 100.0
        assert result["size"] == pytest.approx(100.0, rel=0.01)

    def test_normalized_position_sizing_with_history(
        self, base_params, sample_ohlc_data
    ):
        """Test normalized position sizing with history."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 110.0,  # 10% return
                "current_price": 100.0,
                "position_sizing": "normalized",
                "threshold_value": 0.05,
                "execution_size": 10.0,
                "which_history": "close",
                "window_history": 20,
            }
        )
        params.update(sample_ohlc_data)

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"
        # Size should be normalized by volatility
        assert result["size"] > 0

    def test_normalized_position_sizing_insufficient_history(self, base_params):
        """Test normalized position sizing falls back to fixed when history insufficient."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 110.0,
                "current_price": 100.0,
                "position_sizing": "normalized",
                "threshold_value": 0.05,
                "execution_size": 10.0,
                "which_history": "close",
                "window_history": 20,
                "close_history": [100.0],  # Insufficient history
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"
        # Should fallback to fixed size
        assert result["size"] == 10.0

    def test_return_threshold_buy(self, base_params):
        """Test return threshold generates buy signal when return > threshold."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 110.0,  # 10% return
                "current_price": 100.0,
                "position_sizing": "fixed",
                "threshold_value": 0.05,  # 5% threshold
                "execution_size": 10.0,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"
        assert "Expected return" in result["reason"]

    def test_return_threshold_sell(self, base_params):
        """Test return threshold generates sell signal when return < -threshold."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 90.0,  # -10% return
                "current_price": 100.0,
                "current_position": 100.0,
                "position_sizing": "fixed",
                "threshold_value": 0.05,  # 5% threshold
                "execution_size": 10.0,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "sell"
        assert "Expected return" in result["reason"]

    def test_return_within_threshold_hold(self, base_params):
        """Test return within threshold generates hold signal."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 102.0,  # 2% return
                "current_price": 100.0,
                "position_sizing": "fixed",
                "threshold_value": 0.05,  # 5% threshold
                "execution_size": 10.0,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "hold"
        assert "within threshold" in result["reason"].lower()
        assert result["size"] == 0

    def test_max_position_size_constraint(self, base_params):
        """Test max_position_size constraint is applied."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 110.0,  # 10% return
                "current_price": 100.0,
                "position_sizing": "proportional",
                "threshold_value": 0.05,
                "execution_size": 10.0,
                "max_position_size": 50.0,  # Limit to 50
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"
        assert result["size"] <= 50.0

    def test_min_position_size_constraint(self, base_params):
        """Test min_position_size constraint is applied."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 101.0,  # 1% return (small)
                "current_price": 100.0,
                "position_sizing": "proportional",
                "threshold_value": 0.005,  # 0.5% threshold (very low)
                "execution_size": 1.0,
                "min_position_size": 5.0,  # Minimum 5
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"
        assert result["size"] >= 5.0

    def test_max_min_position_size_validation(self, base_params):
        """Test that max_position_size >= min_position_size validation works."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 110.0,
                "current_price": 100.0,
                "position_sizing": "fixed",
                "threshold_value": 0.05,
                "execution_size": 10.0,
                "max_position_size": 5.0,  # Less than min
                "min_position_size": 10.0,  # Greater than max
            }
        )

        with pytest.raises(InvalidParametersError):
            TradingStrategy.execute_trading_signal(params)

    def test_zero_return(self, base_params):
        """Test edge case: zero return (forecast == current price)."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "forecast_price": 100.0,  # Same as current
                "current_price": 100.0,
                "position_sizing": "fixed",
                "threshold_value": 0.05,
                "execution_size": 10.0,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        # Zero return should be within threshold, so hold
        assert result["action"] == "hold"
        assert result["size"] == 0

    def test_invalid_position_sizing(self, base_params):
        """Test invalid position_sizing raises error."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "return",
                "position_sizing": "invalid_sizing",
                "threshold_value": 0.05,
                "execution_size": 10.0,
            }
        )

        with pytest.raises(InvalidParametersError):
            TradingStrategy.execute_trading_signal(params)
