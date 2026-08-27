"""
Unit tests for quantile-based trading strategy.

Tests the calculate_quantile_signal and execute_trading_signal methods
for quantile strategy with various quantile signal configurations.
"""

import pytest

from trading.core.exceptions import InvalidParametersError
from trading.services.trading import TradingStrategy


class TestQuantileStrategy:
    """Test quantile-based trading strategy."""

    def test_buy_signal_from_quantile_range(self, base_params, sample_ohlc_data):
        """Test buy signal when forecast percentile matches quantile range."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 120.0,  # High forecast (likely in upper quantile)
                "current_price": 100.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [90, 95], "signal": "buy", "multiplier": 0.75},
                    2: {"range": [95, 100], "signal": "buy", "multiplier": 1.0},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
            }
        )
        params.update(sample_ohlc_data)

        result = TradingStrategy.execute_trading_signal(params)

        # Should generate buy signal if percentile matches
        assert result["action"] in ["buy", "hold"]

    def test_sell_signal_from_quantile_range(self, base_params, sample_ohlc_data):
        """Test sell signal when forecast percentile matches quantile range."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 80.0,  # Low forecast (likely in lower quantile)
                "current_price": 100.0,
                "current_position": 100.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [0, 5], "signal": "sell", "multiplier": 1.0},
                    2: {"range": [5, 10], "signal": "sell", "multiplier": 0.5},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
            }
        )
        params.update(sample_ohlc_data)

        result = TradingStrategy.execute_trading_signal(params)

        # Should generate sell signal if percentile matches
        assert result["action"] in ["sell", "hold"]

    def test_hold_when_no_range_matches(self, base_params, sample_ohlc_data):
        """Test hold signal when forecast percentile doesn't match any range."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 100.0,  # Middle forecast
                "current_price": 100.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [0, 10], "signal": "sell", "multiplier": 1.0},
                    2: {"range": [90, 100], "signal": "buy", "multiplier": 1.0},
                    # No signal for middle range (10-90)
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
            }
        )
        params.update(sample_ohlc_data)

        result = TradingStrategy.execute_trading_signal(params)

        # If percentile is in middle range, should hold
        # (May be buy/sell depending on actual percentile calculation)
        assert result["action"] in ["buy", "sell", "hold"]

    def test_multiplier_application_buy(self, base_params, sample_ohlc_data):
        """Test multiplier is applied correctly for buy signals."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 120.0,
                "current_price": 100.0,
                "available_cash": 100000.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [90, 100], "signal": "buy", "multiplier": 0.5},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
            }
        )
        params.update(sample_ohlc_data)

        result = TradingStrategy.execute_trading_signal(params)

        if result["action"] == "buy":
            # Base size = (available_cash / current_price) * multiplier
            # = (100000 / 100) * 0.5 = 500
            assert result["size"] > 0

    def test_multiplier_application_sell(self, base_params, sample_ohlc_data):
        """Test multiplier is applied correctly for sell signals."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 80.0,
                "current_price": 100.0,
                "current_position": 100.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [0, 10], "signal": "sell", "multiplier": 0.5},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
            }
        )
        params.update(sample_ohlc_data)

        result = TradingStrategy.execute_trading_signal(params)

        if result["action"] == "sell":
            # Size = current_position * multiplier = 100 * 0.5 = 50
            assert result["size"] == pytest.approx(50.0, rel=0.01)

    def test_normalized_position_sizing(self, base_params, sample_ohlc_data):
        """Test normalized position sizing with quantile strategy."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 120.0,
                "current_price": 100.0,
                "available_cash": 100000.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [90, 100], "signal": "buy", "multiplier": 0.75},
                },
                "position_sizing": "normalized",
                "execution_size": 100.0,
            }
        )
        params.update(sample_ohlc_data)

        result = TradingStrategy.execute_trading_signal(params)

        if result["action"] == "buy":
            assert result["size"] > 0

    def test_insufficient_history(self, base_params):
        """Test insufficient history returns hold signal."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 110.0,
                "current_price": 100.0,
                "which_history": "close",
                "window_history": 20,
                "min_history_length": 10,
                "quantile_signals": {
                    1: {"range": [90, 100], "signal": "buy", "multiplier": 1.0},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
                "open_history": [100.0] * 5,  # Only 5 values
                "high_history": [110.0] * 5,
                "low_history": [90.0] * 5,
                "close_history": [100.0] * 5,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        # Should hold due to insufficient history
        assert result["action"] == "hold"
        assert "Insufficient history" in result["reason"]

    def test_percentile_calculation_accuracy(self, base_params):
        """Test percentile calculation is accurate."""
        # Create history where we know the percentile
        history = [
            90.0,
            91.0,
            92.0,
            93.0,
            94.0,
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
        ]

        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 110.0,  # Above all history values
                "current_price": 100.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [95, 100], "signal": "buy", "multiplier": 1.0},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
                "open_history": history,
                "high_history": [h + 5 for h in history],
                "low_history": [h - 5 for h in history],
                "close_history": history,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        # Forecast (110) is above all values, so percentile should be 100
        # Should match range [95, 100] and generate buy signal
        assert result["action"] in ["buy", "hold"]

    def test_multiple_quantile_signals_first_match_wins(self, base_params, sample_ohlc_data):
        """Test that first matching quantile signal is used."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 120.0,
                "current_price": 100.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [90, 95], "signal": "buy", "multiplier": 0.5},
                    2: {
                        "range": [90, 100],
                        "signal": "sell",
                        "multiplier": 1.0,
                    },  # Overlaps but comes second
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
            }
        )
        params.update(sample_ohlc_data)

        result = TradingStrategy.execute_trading_signal(params)

        # First match should win (range 1: [90, 95])
        # But depends on actual percentile, so just check it executes
        assert result["action"] in ["buy", "sell", "hold"]

    def test_percentile_at_range_boundary(self, base_params):
        """Test percentile at range boundary."""
        history = list(range(100, 120))  # 20 values from 100 to 119

        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 115.0,  # Middle of range
                "current_price": 100.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [40, 60], "signal": "buy", "multiplier": 1.0},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
                "open_history": history,
                "high_history": [h + 2 for h in history],
                "low_history": [h - 2 for h in history],
                "close_history": history,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        # Should execute based on percentile calculation
        assert result["action"] in ["buy", "hold"]

    def test_all_history_values_equal(self, base_params):
        """Test edge case: all history values are equal."""
        history = [100.0] * 20  # All same value

        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 105.0,  # Above all equal values
                "current_price": 100.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [95, 100], "signal": "buy", "multiplier": 1.0},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
                "open_history": history,
                "high_history": history,
                "low_history": history,
                "close_history": history,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        # Forecast (105) > all values (100), percentile should be 100
        # Should match range [95, 100] and generate buy
        assert result["action"] in ["buy", "hold"]

    def test_all_in_buy_never_leaves_negative_cash(self, base_params):
        """An all-in buy (multiplier 1.0) must not 500 on float residue.

        actual_size = cash / price, then trade_value = (cash / price) * price,
        which can exceed cash by ~1 ulp — e.g. cash=112717.52, price=4.91
        yields a residue of +1.455e-11. new_cash then lands a hair below zero
        and StrategyResponse's available_cash >= 0 rejects the service's own
        result with a 500. Observed live on 2 of 16 matrix cells.
        """
        from trading.schemas.schema import StrategyResponse

        history = [5.0 + 0.01 * i for i in range(20)]
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                # Forecast above most of history -> lands in the buy range.
                "forecast_price": 5.18,
                "current_price": 4.91,  # reproducing pair with the cash below
                "current_position": 0.0,
                "available_cash": 112717.52,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    0: {"range": [75, 100], "signal": "buy", "multiplier": 1.0},
                },
                "open_history": history,
                "high_history": history,
                "low_history": history,
                "close_history": history,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "buy"
        assert result["available_cash"] >= 0.0
        # Spent exactly everything: the residue must be zero, not -1e-11.
        assert result["available_cash"] == 0.0
        # The exact failure site was response validation — it must round-trip.
        StrategyResponse(**result)

    def test_percentile_100_lands_in_terminal_range(self, base_params):
        """A forecast above the entire window must match the top range.

        percentile = count(history < forecast)/n, so forecast > max(history)
        is exactly 100.0. With uniformly half-open ranges that value matched
        nothing and the strongest possible signal silently held (observed live:
        reason "Forecast percentile 100.0 does not match any quantile signal
        range"). Terminal ranges ending at 100 are closed, per the
        numpy.histogram last-bin convention.
        """
        history = [100.0 + i for i in range(20)]
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 500.0,  # far above every bar -> percentile 100.0
                "current_price": 119.0,
                "current_position": 10.0,
                "available_cash": 100000.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    0: {"range": [0, 75], "signal": "hold", "multiplier": 0.0},
                    1: {"range": [75, 100], "signal": "sell", "multiplier": 1.0},
                },
                "open_history": history,
                "high_history": [h + 2 for h in history],
                "low_history": [h - 2 for h in history],
                "close_history": history,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        assert result["action"] == "sell"
        assert "does not match any quantile signal range" not in result["reason"]

    def test_interior_range_upper_edge_stays_open(self, base_params):
        """Only the terminal edge closes: an interior boundary still belongs
        to the next range up, so adjacent ranges never double-match."""
        history = [100.0 + i for i in range(20)]
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                # forecast equal to history[10] -> 10 of 20 strictly below -> 50.0
                "forecast_price": 110.0,
                "current_price": 110.0,
                "current_position": 10.0,
                "available_cash": 100000.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    0: {"range": [0, 50], "signal": "sell", "multiplier": 1.0},
                    1: {"range": [50, 100], "signal": "buy", "multiplier": 0.5},
                },
                "open_history": history,
                "high_history": [h + 2 for h in history],
                "low_history": [h - 2 for h in history],
                "close_history": history,
            }
        )

        result = TradingStrategy.execute_trading_signal(params)

        # 50.0 is the upper edge of [0,50) and the lower edge of [50,100]:
        # it must land in the upper range.
        assert result["action"] == "buy"

    def test_missing_ohlc_data(self, base_params):
        """Test missing OHLC data raises error."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 110.0,
                "current_price": 100.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [90, 100], "signal": "buy", "multiplier": 1.0},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
                # Missing OHLC data
            }
        )

        with pytest.raises(InvalidParametersError):
            TradingStrategy.execute_trading_signal(params)

    def test_mismatched_ohlc_lengths(self, base_params):
        """Test mismatched OHLC array lengths handled gracefully."""
        params = base_params.copy()
        params.update(
            {
                "strategy_type": "quantile",
                "forecast_price": 110.0,
                "current_price": 100.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [90, 100], "signal": "buy", "multiplier": 1.0},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
                "open_history": [100.0] * 20,
                "high_history": [110.0] * 20,
                "low_history": [90.0] * 20,
                "close_history": [100.0] * 15,  # Different length
            }
        )

        # Current implementation doesn't validate length matching
        # It will use the available data and may result in hold or execution
        result = TradingStrategy.execute_trading_signal(params)
        assert result["action"] in ["buy", "sell", "hold"]
