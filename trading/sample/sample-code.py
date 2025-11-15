import numpy as np
from typing import Dict, Optional
from enum import Enum


# Optional Enum classes for type safety (string inputs still work)
class StrategyType(Enum):
    THRESHOLD = "threshold"
    RETURN = "return"
    QUANTILE = "quantile"


class ThresholdType(Enum):
    ABSOLUTE = "absolute"
    PERCENTAGE = "percentage"
    STD_DEV = "std_dev"
    ATR = "atr"
    RETURN = "return"


class PositionSizing(Enum):
    FIXED = "fixed"
    PROPORTIONAL = "proportional"
    NORMALIZED = "normalized"


class WhichHistory(Enum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"


class TradingStrategy:
    """
    Stateless trading strategy implementation for long-only positions.
    All state (position, capital) comes from orchestrator via parameters.
    """

    @staticmethod
    def execute_trading_signal(params: Dict) -> Dict:
        """
        Execute trading signal with capital management

        Required params:
            - strategy_type: str
            - forecast_price: float
            - current_price: float
            - current_position: float (from orchestrator)
            - available_cash: float (from orchestrator)
            - initial_capital: float
            - (strategy-specific params)

        Returns:
            Dict with keys: {
                'action': 'buy', 'sell', or 'hold',
                'size': position size (shares/units),
                'value': dollar value of trade,
                'reason': explanation,
                'available_cash': cash after trade,
                'position_after': position after trade,
                'stopped': bool indicating if strategy stopped (out of cash and position)
            }
        """
        # Extract common parameters
        current_position = params["current_position"]
        available_cash = params["available_cash"]
        current_price = params["current_price"]

        # Check if already stopped (no capital left)
        if available_cash <= 0 and current_position <= 0:
            return {
                "action": "hold",
                "size": 0,
                "value": 0,
                "reason": "Strategy stopped: no capital remaining",
                "available_cash": 0,
                "position_after": 0,
                "stopped": True,
            }

        # Generate signal
        signal = TradingStrategy.generate_trading_signal(params)

        # Initialize result
        result = {
            "action": signal["action"],
            "size": 0,
            "value": 0,
            "reason": signal["reason"],
            "available_cash": available_cash,
            "position_after": current_position,
            "stopped": False,
        }

        # Execute based on action (optimized)
        if signal["action"] == "hold":
            return result

        # Calculate how much we can buy/sell
        max_affordable = available_cash / current_price
        desired_size = signal["size"]

        if signal["action"] == "buy":
            # Can only buy what we can afford
            actual_size = min(desired_size, max_affordable)

            if actual_size <= 0:
                result["action"] = "hold"
                result["reason"] = "Insufficient cash to buy"
                return result

            sign = 1.0

        elif signal["action"] == "sell":
            # Can only sell what we have
            actual_size = min(desired_size, current_position)

            if actual_size <= 0:
                result["action"] = "hold"
                result["reason"] = "No position to sell"
                return result

            sign = -1.0

        else:
            return result

        # Execute trade
        trade_value = actual_size * current_price
        new_cash = available_cash - sign * trade_value
        new_position = current_position + sign * actual_size

        result["size"] = actual_size
        result["value"] = trade_value
        result["available_cash"] = new_cash
        result["position_after"] = new_position

        # Check if strategy should stop (orchestrator will handle this, but we flag it)
        if result["available_cash"] <= 0 and result["position_after"] <= 0:
            result["stopped"] = True
            result["reason"] += " | Strategy stopped: capital exhausted"

        return result

    @staticmethod
    def generate_trading_signal(params: Dict) -> Dict:
        """
        Generate trading signal based on strategy type

        Returns:
            Dict with keys: {
                'action': 'buy', 'sell', or 'hold',
                'size': recommended position size,
                'reason': explanation string
            }
        """
        strategy_type = params.get("strategy_type", "threshold")

        if (
            strategy_type == "threshold"
            or strategy_type == StrategyType.THRESHOLD.value
        ):
            return TradingStrategy.calculate_threshold_signal(params)

        elif strategy_type == "return" or strategy_type == StrategyType.RETURN.value:
            return TradingStrategy.calculate_return_signal(params)

        elif (
            strategy_type == "quantile" or strategy_type == StrategyType.QUANTILE.value
        ):
            return TradingStrategy.calculate_quantile_signal(params)

        else:
            return {
                "action": "hold",
                "size": 0,
                "reason": f"Unknown strategy type: {strategy_type}",
            }

    @staticmethod
    def calculate_threshold_signal(params: Dict) -> Dict:
        """
        Threshold-based strategy (includes sign-based as special case with threshold_value=0)

        Required params:
            - forecast_price: float
            - current_price: float
            - current_position: float
            - threshold_type: str ('absolute', 'percentage', 'std_dev', 'atr')
            - threshold_value: float (threshold value/multiplier)

        Conditional params:
            - open_history, high_history, low_history, close_history: np.array (for 'atr')
            - which_history: str ('open', 'high', 'low', 'close') (for 'std_dev')
            - window_history: int (for 'std_dev', 'atr')

        Optional params:
            - execution_size: float (default: 1.0)
            - min_history_length: int (default: 2)
        """
        forecast_price = params["forecast_price"]
        current_price = params["current_price"]
        current_position = params["current_position"]
        threshold_type = params.get("threshold_type", "absolute")
        threshold_value = params.get("threshold_value", 0.0)
        execution_size = params.get("execution_size", 1.0)

        # Calculate threshold
        threshold = TradingStrategy._calculate_threshold(
            threshold_type,
            threshold_value,
            params.get("open_history"),
            params.get("high_history"),
            params.get("low_history"),
            params.get("close_history"),
            params.get("which_history", "close"),
            params.get("window_history", 20),
            params.get("min_history_length", 2),
            current_price,
        )

        # Calculate signal magnitude and direction
        price_diff = forecast_price - current_price
        signal_magnitude = abs(price_diff)

        # Check if signal exceeds threshold
        if signal_magnitude < threshold:
            return {
                "action": "hold",
                "size": 0,
                "reason": f"Signal {signal_magnitude:.4f} below threshold {threshold:.4f}",
            }

        # Signal exceeds threshold - determine action
        if price_diff > 0:
            # Forecast > Price: Buy signal
            return {
                "action": "buy",
                "size": execution_size,
                "reason": f"Forecast {forecast_price:.2f} > Price {current_price:.2f}, magnitude {signal_magnitude:.4f} > threshold {threshold:.4f}",
            }
        else:
            # Forecast < Price: Sell signal (sell execution_size amount)
            return {
                "action": "sell",
                "size": execution_size,
                "reason": f"Forecast {forecast_price:.2f} < Price {current_price:.2f}, magnitude {signal_magnitude:.4f} > threshold {threshold:.4f}",
            }

    @staticmethod
    def calculate_return_signal(params: Dict) -> Dict:
        """
        Forecast return-based strategy with position sizing and return threshold

        Required params:
            - forecast_price: float
            - current_price: float
            - current_position: float
            - position_sizing: str ('fixed', 'proportional', 'normalized')
            - threshold_type: str ('return')
            - threshold_value: float (return threshold, e.g., 0.05 for 5%)

        Conditional params:
            - open_history, high_history, low_history, close_history: np.array (for 'normalized')
            - which_history: str ('open', 'high', 'low', 'close') (for 'normalized')
            - window_history: int (for 'normalized')

        Optional params:
            - execution_size: float (default: 1.0)
            - max_position_size: float
            - min_position_size: float
            - min_history_length: int (default: 2)
        """
        forecast_price = params["forecast_price"]
        current_price = params["current_price"]
        current_position = params["current_position"]
        position_sizing = params.get("position_sizing", "fixed")
        threshold_value = params.get("threshold_value", 0.0)
        execution_size = params.get("execution_size", 1.0)
        max_position_size = params.get("max_position_size", None)
        min_position_size = params.get("min_position_size", None)

        # Calculate expected return
        expected_return = (forecast_price - current_price) / current_price

        # Check if expected return exceeds threshold
        if expected_return > threshold_value:
            # Positive return above threshold: Buy signal
            action = "buy"
        elif expected_return < -threshold_value:
            # Negative return below threshold: Sell signal
            action = "sell"
        else:
            # Return within threshold: Hold
            return {
                "action": "hold",
                "size": 0,
                "reason": f"Expected return {expected_return:.2%} within threshold ±{threshold_value:.2%}",
            }

        # Determine position size based on sizing method
        if position_sizing == "fixed" or position_sizing == PositionSizing.FIXED.value:
            position_size = execution_size

        elif (
            position_sizing == "proportional"
            or position_sizing == PositionSizing.PROPORTIONAL.value
        ):
            # Scale position by expected return magnitude
            # e.g., 10% expected return → 10x execution_size, 1% → 1x execution_size
            position_size = (
                execution_size * abs(expected_return) * 100
            )  # *100 to convert decimal to %

        elif (
            position_sizing == "normalized"
            or position_sizing == PositionSizing.NORMALIZED.value
        ):
            # Normalize by recent return volatility
            which_history = params.get("which_history", "close")
            history_array = TradingStrategy._get_history_array(params, which_history)
            window_history = params.get("window_history", 20)
            min_history_length = params.get("min_history_length", 2)

            if history_array is None or len(history_array) < min_history_length:
                # Fallback to fixed if no history
                position_size = execution_size
            else:
                recent_history = history_array[-window_history:]
                return_history = TradingStrategy._calculate_returns(recent_history)
                return_std = np.std(return_history)

                if return_std == 0:
                    position_size = execution_size
                else:
                    # Scale by expected return relative to historical volatility
                    normalized_return = abs(expected_return) / return_std
                    position_size = execution_size * normalized_return
        else:
            position_size = execution_size

        # Apply position size constraints if provided
        if max_position_size is not None:
            position_size = min(position_size, max_position_size)
        if min_position_size is not None:
            position_size = max(position_size, min_position_size)

        # Return signal
        return {
            "action": action,
            "size": position_size,
            "reason": f"Expected return: {expected_return:.2%} (threshold: ±{threshold_value:.2%}), position size: {position_size:.2f}",
        }

    @staticmethod
    def calculate_quantile_signal(params: Dict) -> Dict:
        """
        Quantile-based strategy using empirical quantiles

        Required params:
            - forecast_price: float
            - current_price: float
            - current_position: float
            - available_cash: float
            - open_history, high_history, low_history, close_history: np.array
            - which_history: str ('open', 'high', 'low', 'close')
            - window_history: int (window for quantile calculation, e.g., 30)
            - quantile_signals: Dict with structure:
                {1: {"range": [0,5], "signal": "sell", "multiplier": 1.0},
                 2: {"range": [5,10], "signal": "sell", "multiplier": 0.5},
                 3: {"range": [90,95], "signal": "buy", "multiplier": 0.75},
                 ...}

        Optional params:
            - position_sizing: str ('fixed', 'normalized'), default: 'fixed'
            - execution_size: float (default: 1.0)
            - max_position_size: float
            - min_position_size: float
            - min_history_length: int (default: 2)
        """
        forecast_price = params["forecast_price"]
        current_price = params["current_price"]
        current_position = params["current_position"]
        available_cash = params["available_cash"]
        which_history = params.get("which_history", "close")
        window_history = params["window_history"]
        quantile_signals = params["quantile_signals"]
        position_sizing = params.get("position_sizing", "fixed")
        execution_size = params.get("execution_size", 1.0)
        max_position_size = params.get("max_position_size", None)
        min_position_size = params.get("min_position_size", None)
        min_history_length = params.get("min_history_length", 2)

        # Get the appropriate history array
        history_array = TradingStrategy._get_history_array(params, which_history)

        if history_array is None:
            return {
                "action": "hold",
                "size": 0,
                "reason": f"No {which_history}_history provided",
            }

        # Get recent history for quantile calculation
        recent_history = history_array[-window_history:]

        if len(recent_history) < min_history_length:
            return {
                "action": "hold",
                "size": 0,
                "reason": f"Insufficient history for quantile calculation (need at least {min_history_length})",
            }

        # Calculate percentile of forecast_price relative to historical distribution
        percentile = np.sum(recent_history < forecast_price) / len(recent_history) * 100

        # Find matching quantile signal
        matched_signal = None
        for key, signal_config in quantile_signals.items():
            range_min, range_max = signal_config["range"]
            if range_min <= percentile < range_max:
                matched_signal = signal_config
                break

        if matched_signal is None:
            return {
                "action": "hold",
                "size": 0,
                "reason": f"Forecast percentile {percentile:.1f} does not match any quantile signal range",
            }

        # Extract signal and multiplier
        signal_action = matched_signal["signal"]
        multiplier = matched_signal["multiplier"]

        # Calculate position size based on signal
        if signal_action == "buy":
            # Buy: multiplier * (available_cash / current_price)
            base_size = (available_cash / current_price) * multiplier

            if (
                position_sizing == "normalized"
                or position_sizing == PositionSizing.NORMALIZED.value
            ):
                # Apply normalized sizing
                return_history = TradingStrategy._calculate_returns(recent_history)
                return_std = np.std(return_history)

                if return_std > 0:
                    expected_return = (forecast_price - current_price) / current_price
                    normalized_return = abs(expected_return) / return_std
                    base_size = base_size * normalized_return

            position_size = base_size

        elif signal_action == "sell":
            # Sell: multiplier * current_position
            position_size = current_position * multiplier

        else:
            return {
                "action": "hold",
                "size": 0,
                "reason": f"Unknown signal action: {signal_action}",
            }

        # Apply position size constraints if provided
        if max_position_size is not None:
            position_size = min(position_size, max_position_size)
        if min_position_size is not None:
            position_size = max(position_size, min_position_size)

        return {
            "action": signal_action,
            "size": position_size,
            "reason": f'Forecast percentile {percentile:.1f} in range {matched_signal["range"]}, signal: {signal_action}, multiplier: {multiplier}',
        }

    # ========== HELPER METHODS ==========

    @staticmethod
    def _get_history_array(params: Dict, which_history: str) -> Optional[np.ndarray]:
        """Get the appropriate history array based on which_history parameter"""
        if which_history == "open" or which_history == WhichHistory.OPEN.value:
            return params.get("open_history")
        elif which_history == "high" or which_history == WhichHistory.HIGH.value:
            return params.get("high_history")
        elif which_history == "low" or which_history == WhichHistory.LOW.value:
            return params.get("low_history")
        elif which_history == "close" or which_history == WhichHistory.CLOSE.value:
            return params.get("close_history")
        else:
            return params.get("close_history")  # Default to close

    @staticmethod
    def _calculate_threshold(
        threshold_type: str,
        threshold_value: float,
        open_history: Optional[np.ndarray],
        high_history: Optional[np.ndarray],
        low_history: Optional[np.ndarray],
        close_history: Optional[np.ndarray],
        which_history: str,
        window_history: int,
        min_history_length: int,
        current_price: float,
    ) -> float:
        """Calculate threshold based on type"""

        if (
            threshold_type == "absolute"
            or threshold_type == ThresholdType.ABSOLUTE.value
        ):
            return threshold_value

        elif (
            threshold_type == "percentage"
            or threshold_type == ThresholdType.PERCENTAGE.value
        ):
            return current_price * (threshold_value / 100.0)

        elif (
            threshold_type == "std_dev" or threshold_type == ThresholdType.STD_DEV.value
        ):
            # Get the appropriate history array
            history_dict = {
                "open_history": open_history,
                "high_history": high_history,
                "low_history": low_history,
                "close_history": close_history,
                "which_history": which_history,
            }
            history_array = TradingStrategy._get_history_array(
                history_dict, which_history
            )

            if history_array is None or len(history_array) < min_history_length:
                # Fallback to absolute
                return threshold_value

            recent_history = history_array[-window_history:]
            history_std = np.std(recent_history)
            return threshold_value * history_std

        elif threshold_type == "atr" or threshold_type == ThresholdType.ATR.value:
            if (
                open_history is None
                or high_history is None
                or low_history is None
                or close_history is None
            ):
                # Fallback to absolute
                return threshold_value

            atr = TradingStrategy._calculate_atr(
                open_history,
                high_history,
                low_history,
                close_history,
                window_history,
                min_history_length,
            )
            return threshold_value * atr

        else:
            # Default to absolute
            return threshold_value

    @staticmethod
    def _calculate_returns(timeseries: np.ndarray) -> np.ndarray:
        """Calculate simple returns from time series"""
        if len(timeseries) < 2:
            return np.array([])

        returns = np.diff(timeseries) / timeseries[:-1]
        return returns

    @staticmethod
    def _calculate_atr(
        open_history: np.ndarray,
        high_history: np.ndarray,
        low_history: np.ndarray,
        close_history: np.ndarray,
        window_history: int,
        min_history_length: int,
    ) -> float:
        """
        Calculate Average True Range using OHLC data
        """
        # Ensure we have enough data
        if (
            len(high_history) < min_history_length
            or len(low_history) < min_history_length
            or len(close_history) < min_history_length
        ):
            return 0.0

        # Take last window_history periods
        high = high_history[-window_history:]
        low = low_history[-window_history:]
        close = close_history[-window_history:]

        # Calculate True Range for each period
        # TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list = []
        for i in range(1, len(high)):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i - 1])
            lc = abs(low[i] - close[i - 1])
            tr = max(hl, hc, lc)
            tr_list.append(tr)

        if len(tr_list) == 0:
            return 0.0

        # ATR is the average of True Ranges
        atr = np.mean(tr_list)
        return atr

    @staticmethod
    def get_portfolio_value(
        current_position: float, current_price: float, available_cash: float
    ) -> float:
        """Calculate total portfolio value (cash + position value)"""
        position_value = current_position * current_price
        return available_cash + position_value

    @staticmethod
    def get_portfolio_return(
        current_position: float,
        current_price: float,
        available_cash: float,
        initial_capital: float,
    ) -> float:
        """Calculate portfolio return relative to initial capital"""
        if initial_capital == 0:
            return 0.0

        current_value = TradingStrategy.get_portfolio_value(
            current_position, current_price, available_cash
        )
        return (current_value - initial_capital) / initial_capital
