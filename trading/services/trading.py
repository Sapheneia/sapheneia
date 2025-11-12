"""
Trading Strategy Implementation

Stateless trading strategy implementation for long-only positions.
Supports three strategy types: threshold, return, and quantile-based strategies.

All state (position, capital) comes from orchestrator via parameters.
"""

import numpy as np
from typing import Dict, Any, Optional, List, Union
from enum import Enum
import logging

from ..core.exceptions import (
    InvalidStrategyError,
    InvalidParametersError,
)
from ..core.config import settings

logger = logging.getLogger(__name__)


# ========== ENUM CLASSES ==========


class StrategyType(Enum):
    """
    Enumeration of supported trading strategy types.

    Attributes:
        THRESHOLD: Threshold-based strategy with configurable threshold types
        RETURN: Return-based strategy with position sizing options
        QUANTILE: Quantile-based strategy using empirical quantiles
    """

    THRESHOLD = "threshold"
    RETURN = "return"
    QUANTILE = "quantile"


class ThresholdType(Enum):
    """
    Enumeration of threshold calculation types for threshold strategy.

    Attributes:
        ABSOLUTE: Absolute price difference threshold
        PERCENTAGE: Percentage-based threshold relative to current price
        STD_DEV: Standard deviation-based threshold using historical volatility
        ATR: Average True Range-based threshold using OHLC data
        RETURN: Return-based threshold (legacy, use return strategy instead)
    """

    ABSOLUTE = "absolute"
    PERCENTAGE = "percentage"
    STD_DEV = "std_dev"
    ATR = "atr"
    RETURN = "return"


class PositionSizing(Enum):
    """
    Enumeration of position sizing methods.

    Attributes:
        FIXED: Fixed position size regardless of signal strength
        PROPORTIONAL: Position size proportional to expected return magnitude
        NORMALIZED: Position size normalized by historical return volatility
    """

    FIXED = "fixed"
    PROPORTIONAL = "proportional"
    NORMALIZED = "normalized"


class WhichHistory(Enum):
    """
    Enumeration of OHLC history types for calculations.

    Attributes:
        OPEN: Open price history
        HIGH: High price history
        LOW: Low price history
        CLOSE: Close price history (most commonly used)
    """

    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"


# ========== TRADING STRATEGY CLASS ==========


class TradingStrategy:
    """
    Stateless trading strategy implementation for long-only positions.

    All state (position, capital) comes from orchestrator via parameters.
    This class provides static methods for strategy execution and signal generation.

    Supported Strategies:
        - Threshold: Price difference-based strategy with configurable thresholds
        - Return: Expected return-based strategy with position sizing
        - Quantile: Empirical quantile-based strategy using historical distribution

    All methods are stateless and can be called concurrently.
    """

    @staticmethod
    def execute_trading_signal(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute trading signal with capital management.

        This is the main entry point for strategy execution. It validates parameters,
        generates a trading signal, and executes the trade with proper capital management.

        Args:
            params: Dictionary containing strategy parameters. Required keys:
                - strategy_type: str - Strategy type ('threshold', 'return', 'quantile')
                - forecast_price: float - Forecasted price (must be > 0)
                - current_price: float - Current market price (must be > 0)
                - current_position: float - Current position size (must be >= 0)
                - available_cash: float - Available cash (must be >= 0)
                - initial_capital: float - Initial capital (must be > 0)
                - Additional strategy-specific parameters (see strategy methods)

        Returns:
            Dictionary with execution results containing:
                - action: str - 'buy', 'sell', or 'hold'
                - size: float - Position size executed (shares/units)
                - value: float - Dollar value of trade
                - reason: str - Explanation of the action
                - available_cash: float - Cash remaining after trade
                - position_after: float - Position size after trade
                - stopped: bool - Whether strategy is stopped (no capital remaining)

        Raises:
            InvalidParametersError: If required parameters are missing or invalid
            StrategyStoppedError: If strategy is stopped (no capital remaining)
            InsufficientCapitalError: If insufficient cash for buy order
            InvalidStrategyError: If strategy type is unknown
        """
        logger.info("Executing trading signal")

        # Validate common parameters
        TradingStrategy._validate_common_params(params)

        # Extract common parameters
        current_position = params["current_position"]
        available_cash = params["available_cash"]
        current_price = params["current_price"]

        # Check if already stopped (no capital left)
        if available_cash <= 0 and current_position <= 0:
            logger.warning("Strategy stopped: no capital remaining")
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
        result: Dict[str, Any] = {
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
            logger.info(f"Hold signal: {signal['reason']}")
            return result

        # Calculate how much we can buy/sell
        max_affordable = available_cash / current_price
        desired_size = signal["size"]

        if signal["action"] == "buy":
            # Can only buy what we can afford
            actual_size = min(desired_size, max_affordable)

            if actual_size <= 0:
                logger.warning(
                    f"Insufficient cash to buy. Available: ${available_cash:.2f}, Required: ${desired_size * current_price:.2f}"
                )
                result["action"] = "hold"
                result["reason"] = "Insufficient cash to buy"
                return result

            sign = 1.0

        elif signal["action"] == "sell":
            # Can only sell what we have
            actual_size = min(desired_size, current_position)

            if actual_size <= 0:
                logger.warning(
                    f"No position to sell. Current position: {current_position:.2f}"
                )
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

        logger.info(
            f"Trade executed: {signal['action'].upper()} {actual_size:.2f} shares "
            f"at ${current_price:.2f} = ${trade_value:.2f}"
        )

        # Check if strategy should stop (orchestrator will handle this, but we flag it)
        if result["available_cash"] <= 0 and result["position_after"] <= 0:
            result["stopped"] = True
            result["reason"] += " | Strategy stopped: capital exhausted"
            logger.warning("Strategy stopped: capital exhausted after trade")

        return result

    @staticmethod
    def generate_trading_signal(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate trading signal based on strategy type.

        Routes to the appropriate strategy-specific signal generation method
        based on the strategy_type parameter.

        Args:
            params: Dictionary containing strategy parameters. Must include:
                - strategy_type: str - Strategy type ('threshold', 'return', 'quantile')
                - Additional parameters required by the specific strategy

        Returns:
            Dictionary with signal information containing:
                - action: str - 'buy', 'sell', or 'hold'
                - size: float - Recommended position size
                - reason: str - Explanation of the signal

        Raises:
            InvalidStrategyError: If strategy type is unknown or invalid
        """
        strategy_type = params.get("strategy_type", "threshold")

        # Normalize strategy type (handle both string and enum values)
        if isinstance(strategy_type, StrategyType):
            strategy_type = strategy_type.value
        strategy_type = str(strategy_type).lower()

        logger.debug(f"Generating signal for strategy type: {strategy_type}")

        if strategy_type == StrategyType.THRESHOLD.value:
            return TradingStrategy.calculate_threshold_signal(params)

        elif strategy_type == StrategyType.RETURN.value:
            return TradingStrategy.calculate_return_signal(params)

        elif strategy_type == StrategyType.QUANTILE.value:
            return TradingStrategy.calculate_quantile_signal(params)

        else:
            error_msg = f"Unknown strategy type: {strategy_type}"
            logger.error(error_msg)
            raise InvalidStrategyError(message=error_msg, strategy_type=strategy_type)

    @staticmethod
    def calculate_threshold_signal(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate threshold-based trading signal.

        Threshold strategy compares the forecast price to current price and generates
        buy/sell signals when the price difference exceeds a configurable threshold.
        Supports multiple threshold types: absolute, percentage, std_dev, and ATR.

        Args:
            params: Dictionary containing threshold strategy parameters. Required:
                - forecast_price: float - Forecasted price
                - current_price: float - Current market price
                - current_position: float - Current position size
                - threshold_type: str - Threshold type ('absolute', 'percentage', 'std_dev', 'atr')
                - threshold_value: float - Threshold value/multiplier (must be >= 0)
            Optional:
                - execution_size: float - Position size to execute (default: 1.0)
                - which_history: str - History type for std_dev ('open', 'high', 'low', 'close')
                - window_history: int - Window size for std_dev/atr calculations (default: 20)
                - min_history_length: int - Minimum history length required (default: 2)
            Conditional (for 'atr' threshold_type):
                - open_history: List[float] or np.ndarray - Open price history
                - high_history: List[float] or np.ndarray - High price history
                - low_history: List[float] or np.ndarray - Low price history
                - close_history: List[float] or np.ndarray - Close price history
            Conditional (for 'std_dev' threshold_type):
                - One of: open_history, high_history, low_history, close_history
                - which_history: str - Which history to use

        Returns:
            Dictionary with signal information:
                - action: str - 'buy', 'sell', or 'hold'
                - size: float - Recommended position size
                - reason: str - Explanation of the signal

        Raises:
            InvalidParametersError: If required parameters are missing or invalid
        """
        # Validate and extract parameters
        forecast_price = params["forecast_price"]
        current_price = params["current_price"]
        current_position = params["current_position"]
        threshold_type = params.get("threshold_type", "absolute")
        threshold_value = params.get("threshold_value", 0.0)
        execution_size = params.get("execution_size", settings.DEFAULT_EXECUTION_SIZE)
        min_history_length = params.get(
            "min_history_length", settings.DEFAULT_MIN_HISTORY_LENGTH
        )

        # Validate threshold parameters
        if threshold_value < 0:
            raise InvalidParametersError(
                message="threshold_value must be non-negative",
                parameter="threshold_value",
                validation_errors={"threshold_value": threshold_value},
            )

        if execution_size <= 0:
            raise InvalidParametersError(
                message="execution_size must be positive",
                parameter="execution_size",
                validation_errors={"execution_size": execution_size},
            )

        # Validate threshold_type
        valid_threshold_types = [e.value for e in ThresholdType]
        if threshold_type not in valid_threshold_types:
            raise InvalidParametersError(
                message=f"Invalid threshold_type: {threshold_type}",
                parameter="threshold_type",
                validation_errors={
                    "threshold_type": threshold_type,
                    "valid_types": valid_threshold_types,
                },
            )

        # Convert history lists to numpy arrays if needed
        open_history = TradingStrategy._convert_to_array(params.get("open_history"))
        high_history = TradingStrategy._convert_to_array(params.get("high_history"))
        low_history = TradingStrategy._convert_to_array(params.get("low_history"))
        close_history = TradingStrategy._convert_to_array(params.get("close_history"))

        # Validate OHLC data for ATR threshold type
        if threshold_type == ThresholdType.ATR.value:
            if (
                open_history is None
                or high_history is None
                or low_history is None
                or close_history is None
            ):
                logger.warning(
                    "ATR threshold requires OHLC data, falling back to absolute threshold"
                )
                threshold_type = "absolute"

        # Calculate threshold
        threshold = TradingStrategy._calculate_threshold(
            threshold_type,
            threshold_value,
            open_history,
            high_history,
            low_history,
            close_history,
            params.get("which_history", "close"),
            params.get("window_history", 20),
            min_history_length,
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
    def calculate_return_signal(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate return-based trading signal with position sizing.

        Return strategy generates buy/sell signals based on expected return relative
        to a threshold. Supports multiple position sizing methods: fixed, proportional,
        and normalized.

        Args:
            params: Dictionary containing return strategy parameters. Required:
                - forecast_price: float - Forecasted price
                - current_price: float - Current market price
                - current_position: float - Current position size
                - position_sizing: str - Position sizing method ('fixed', 'proportional', 'normalized')
                - threshold_value: float - Return threshold (e.g., 0.05 for 5%, must be >= 0)
            Optional:
                - execution_size: float - Base execution size (default: 1.0)
                - max_position_size: float - Maximum position size constraint
                - min_position_size: float - Minimum position size constraint
                - which_history: str - History type for normalized sizing
                - window_history: int - Window size for normalized sizing (default: 20)
                - min_history_length: int - Minimum history length (default: 2)
            Conditional (for 'normalized' position_sizing):
                - One of: open_history, high_history, low_history, close_history
                - which_history: str - Which history to use

        Returns:
            Dictionary with signal information:
                - action: str - 'buy', 'sell', or 'hold'
                - size: float - Recommended position size
                - reason: str - Explanation of the signal

        Raises:
            InvalidParametersError: If required parameters are missing or invalid
        """
        # Extract parameters
        forecast_price = params["forecast_price"]
        current_price = params["current_price"]
        current_position = params["current_position"]
        position_sizing = params.get("position_sizing", "fixed")
        threshold_value = params.get("threshold_value", 0.0)
        execution_size = params.get("execution_size", settings.DEFAULT_EXECUTION_SIZE)
        max_position_size = params.get("max_position_size", None)
        min_position_size = params.get("min_position_size", None)
        min_history_length = params.get(
            "min_history_length", settings.DEFAULT_MIN_HISTORY_LENGTH
        )

        # Validate parameters
        if threshold_value < 0:
            raise InvalidParametersError(
                message="threshold_value must be non-negative",
                parameter="threshold_value",
            )

        if execution_size <= 0:
            raise InvalidParametersError(
                message="execution_size must be positive", parameter="execution_size"
            )

        valid_position_sizing = [e.value for e in PositionSizing]
        if position_sizing not in valid_position_sizing:
            raise InvalidParametersError(
                message=f"Invalid position_sizing: {position_sizing}",
                parameter="position_sizing",
                validation_errors={
                    "position_sizing": position_sizing,
                    "valid_types": valid_position_sizing,
                },
            )

        if max_position_size is not None and min_position_size is not None:
            if max_position_size < min_position_size:
                raise InvalidParametersError(
                    message="max_position_size must be >= min_position_size",
                    parameter="position_size_constraints",
                )

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
        if position_sizing == PositionSizing.FIXED.value:
            position_size = execution_size

        elif position_sizing == PositionSizing.PROPORTIONAL.value:
            # Scale position by expected return magnitude
            # e.g., 10% expected return → 10x execution_size, 1% → 1x execution_size
            position_size = (
                execution_size * abs(expected_return) * 100
            )  # *100 to convert decimal to %

        elif position_sizing == PositionSizing.NORMALIZED.value:
            # Normalize by recent return volatility
            which_history = params.get("which_history", "close")
            history_array = TradingStrategy._get_history_array(params, which_history)
            window_history = params.get("window_history", 20)

            if history_array is None or len(history_array) < min_history_length:
                # Fallback to fixed if no history
                logger.warning(
                    f"Insufficient history for normalized sizing, falling back to fixed. History length: {len(history_array) if history_array is not None else 0}"
                )
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
    def calculate_quantile_signal(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate quantile-based trading signal using empirical quantiles.

        Quantile strategy calculates the percentile of the forecast price relative to
        historical price distribution and generates signals based on quantile ranges.

        Args:
            params: Dictionary containing quantile strategy parameters. Required:
                - forecast_price: float - Forecasted price
                - current_price: float - Current market price
                - current_position: float - Current position size
                - available_cash: float - Available cash
                - which_history: str - History type to use ('open', 'high', 'low', 'close')
                - window_history: int - Window size for quantile calculation (must be > 0)
                - quantile_signals: Dict - Quantile signal configuration with structure:
                    {
                        key: {
                            "range": [min_percentile, max_percentile],
                            "signal": "buy" | "sell" | "hold",
                            "multiplier": float (0.0 to 1.0)
                        },
                        ...
                    }
                - open_history: List[float] or np.ndarray - Open price history (required)
                - high_history: List[float] or np.ndarray - High price history (required)
                - low_history: List[float] or np.ndarray - Low price history (required)
                - close_history: List[float] or np.ndarray - Close price history (required)
            Optional:
                - position_sizing: str - Position sizing method ('fixed' or 'normalized', default: 'fixed')
                - execution_size: float - Base execution size (default: 1.0)
                - max_position_size: float - Maximum position size constraint
                - min_position_size: float - Minimum position size constraint
                - min_history_length: int - Minimum history length (default: 2)

        Returns:
            Dictionary with signal information:
                - action: str - 'buy', 'sell', or 'hold'
                - size: float - Recommended position size
                - reason: str - Explanation of the signal

        Raises:
            InvalidParametersError: If required parameters are missing or invalid
        """
        # Extract and validate parameters
        forecast_price = params["forecast_price"]
        current_price = params["current_price"]
        current_position = params["current_position"]
        available_cash = params["available_cash"]
        which_history = params.get("which_history", "close")
        window_history = params.get("window_history")
        quantile_signals = params.get("quantile_signals")
        position_sizing = params.get("position_sizing", "fixed")
        execution_size = params.get("execution_size", settings.DEFAULT_EXECUTION_SIZE)
        max_position_size = params.get("max_position_size", None)
        min_position_size = params.get("min_position_size", None)
        min_history_length = params.get(
            "min_history_length", settings.DEFAULT_MIN_HISTORY_LENGTH
        )

        # Validate required parameters
        if window_history is None or window_history <= 0:
            raise InvalidParametersError(
                message="window_history must be positive", parameter="window_history"
            )

        if quantile_signals is None or not isinstance(quantile_signals, dict):
            raise InvalidParametersError(
                message="quantile_signals must be a dictionary",
                parameter="quantile_signals",
            )

        # Validate quantile_signals structure
        for key, signal_config in quantile_signals.items():
            if not isinstance(signal_config, dict):
                raise InvalidParametersError(
                    message=f"quantile_signals[{key}] must be a dictionary",
                    parameter="quantile_signals",
                )

            required_keys = ["range", "signal", "multiplier"]
            for req_key in required_keys:
                if req_key not in signal_config:
                    raise InvalidParametersError(
                        message=f"quantile_signals[{key}] missing required key: {req_key}",
                        parameter="quantile_signals",
                    )

            # Validate range
            if (
                not isinstance(signal_config["range"], list)
                or len(signal_config["range"]) != 2
            ):
                raise InvalidParametersError(
                    message=f"quantile_signals[{key}]['range'] must be a list of 2 elements",
                    parameter="quantile_signals",
                )

            range_min, range_max = signal_config["range"]
            if range_min < 0 or range_max > 100 or range_min >= range_max:
                raise InvalidParametersError(
                    message=f"quantile_signals[{key}]['range'] must be [min, max] where 0 <= min < max <= 100",
                    parameter="quantile_signals",
                )

            # Validate signal
            if signal_config["signal"] not in ["buy", "sell", "hold"]:
                raise InvalidParametersError(
                    message=f"quantile_signals[{key}]['signal'] must be 'buy', 'sell', or 'hold'",
                    parameter="quantile_signals",
                )

            # Validate multiplier
            multiplier = signal_config["multiplier"]
            if (
                not isinstance(multiplier, (int, float))
                or multiplier < 0
                or multiplier > 1
            ):
                raise InvalidParametersError(
                    message=f"quantile_signals[{key}]['multiplier'] must be between 0 and 1",
                    parameter="quantile_signals",
                )

        # Validate which_history
        valid_history_types = [e.value for e in WhichHistory]
        if which_history not in valid_history_types:
            raise InvalidParametersError(
                message=f"Invalid which_history: {which_history}",
                parameter="which_history",
                validation_errors={
                    "which_history": which_history,
                    "valid_types": valid_history_types,
                },
            )

        # Convert history lists to numpy arrays
        open_history = TradingStrategy._convert_to_array(params.get("open_history"))
        high_history = TradingStrategy._convert_to_array(params.get("high_history"))
        low_history = TradingStrategy._convert_to_array(params.get("low_history"))
        close_history = TradingStrategy._convert_to_array(params.get("close_history"))

        # Validate OHLC data is provided
        if (
            open_history is None
            or high_history is None
            or low_history is None
            or close_history is None
        ):
            raise InvalidParametersError(
                message="All OHLC histories (open_history, high_history, low_history, close_history) are required for quantile strategy",
                parameter="ohlc_history",
            )

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

            if position_sizing == PositionSizing.NORMALIZED.value:
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

        else:  # hold
            return {
                "action": "hold",
                "size": 0,
                "reason": f"Signal action is hold for percentile {percentile:.1f}",
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
    def _validate_common_params(params: Dict[str, Any]) -> None:
        """
        Validate common parameters required by all strategies.

        Args:
            params: Dictionary containing parameters

        Raises:
            InvalidParametersError: If any required parameter is missing or invalid
        """
        required_params = [
            "forecast_price",
            "current_price",
            "current_position",
            "available_cash",
            "initial_capital",
        ]

        for param in required_params:
            if param not in params:
                raise InvalidParametersError(
                    message=f"Missing required parameter: {param}", parameter=param
                )

        # Validate forecast_price
        forecast_price = params["forecast_price"]
        if not isinstance(forecast_price, (int, float)) or forecast_price <= 0:
            raise InvalidParametersError(
                message="forecast_price must be a positive number",
                parameter="forecast_price",
                validation_errors={"forecast_price": forecast_price},
            )

        # Validate current_price
        current_price = params["current_price"]
        if not isinstance(current_price, (int, float)) or current_price <= 0:
            raise InvalidParametersError(
                message="current_price must be a positive number",
                parameter="current_price",
                validation_errors={"current_price": current_price},
            )

        # Validate current_position (long-only: must be >= 0)
        current_position = params["current_position"]
        if not isinstance(current_position, (int, float)) or current_position < 0:
            raise InvalidParametersError(
                message="current_position must be non-negative (long-only positions)",
                parameter="current_position",
                validation_errors={"current_position": current_position},
            )

        # Validate available_cash
        available_cash = params["available_cash"]
        if not isinstance(available_cash, (int, float)) or available_cash < 0:
            raise InvalidParametersError(
                message="available_cash must be non-negative",
                parameter="available_cash",
                validation_errors={"available_cash": available_cash},
            )

        # Validate initial_capital
        initial_capital = params["initial_capital"]
        if not isinstance(initial_capital, (int, float)) or initial_capital <= 0:
            raise InvalidParametersError(
                message="initial_capital must be a positive number",
                parameter="initial_capital",
                validation_errors={"initial_capital": initial_capital},
            )

    @staticmethod
    def _convert_to_array(
        data: Optional[Union[List[float], np.ndarray]],
    ) -> Optional[np.ndarray]:
        """
        Convert list to numpy array if needed.

        Args:
            data: List of floats or numpy array or None

        Returns:
            Numpy array or None
        """
        if data is None:
            return None
        if isinstance(data, np.ndarray):
            return data
        if isinstance(data, list):
            return np.array(data)
        return None

    @staticmethod
    def _get_history_array(
        params: Dict[str, Any], which_history: str
    ) -> Optional[np.ndarray]:
        """
        Get the appropriate history array based on which_history parameter.

        Args:
            params: Dictionary containing history arrays
            which_history: History type ('open', 'high', 'low', 'close')

        Returns:
            Numpy array of history data or None if not found
        """
        # Convert to array if needed
        if which_history == WhichHistory.OPEN.value or which_history == "open":
            return TradingStrategy._convert_to_array(params.get("open_history"))
        elif which_history == WhichHistory.HIGH.value or which_history == "high":
            return TradingStrategy._convert_to_array(params.get("high_history"))
        elif which_history == WhichHistory.LOW.value or which_history == "low":
            return TradingStrategy._convert_to_array(params.get("low_history"))
        elif which_history == WhichHistory.CLOSE.value or which_history == "close":
            return TradingStrategy._convert_to_array(params.get("close_history"))
        else:
            # Default to close
            return TradingStrategy._convert_to_array(params.get("close_history"))

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
        """
        Calculate threshold based on type.

        Args:
            threshold_type: Type of threshold ('absolute', 'percentage', 'std_dev', 'atr')
            threshold_value: Threshold value/multiplier
            open_history: Open price history (for ATR)
            high_history: High price history (for ATR)
            low_history: Low price history (for ATR)
            close_history: Close price history (for ATR and std_dev)
            which_history: History type to use for std_dev
            window_history: Window size for calculations
            min_history_length: Minimum history length required
            current_price: Current market price (for percentage calculation)

        Returns:
            Calculated threshold value
        """
        if (
            threshold_type == ThresholdType.ABSOLUTE.value
            or threshold_type == "absolute"
        ):
            return threshold_value

        elif (
            threshold_type == ThresholdType.PERCENTAGE.value
            or threshold_type == "percentage"
        ):
            return current_price * (threshold_value / 100.0)

        elif (
            threshold_type == ThresholdType.STD_DEV.value or threshold_type == "std_dev"
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
                logger.warning(
                    f"Insufficient history for std_dev threshold, falling back to absolute. History length: {len(history_array) if history_array is not None else 0}"
                )
                return threshold_value

            recent_history = history_array[-window_history:]
            history_std = np.std(recent_history)
            return threshold_value * history_std

        elif threshold_type == ThresholdType.ATR.value or threshold_type == "atr":
            if (
                open_history is None
                or high_history is None
                or low_history is None
                or close_history is None
            ):
                # Fallback to absolute
                logger.warning(
                    "Missing OHLC data for ATR threshold, falling back to absolute"
                )
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
            logger.warning(f"Unknown threshold_type: {threshold_type}, using absolute")
            return threshold_value

    @staticmethod
    def _calculate_returns(timeseries: np.ndarray) -> np.ndarray:
        """
        Calculate simple returns from time series.

        Args:
            timeseries: Numpy array of price values

        Returns:
            Numpy array of returns (one less element than input)
        """
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
        Calculate Average True Range (ATR) using OHLC data.

        ATR measures market volatility by calculating the average of True Ranges
        over a specified window. True Range is the maximum of:
        - High - Low
        - abs(High - Previous Close)
        - abs(Low - Previous Close)

        Args:
            open_history: Open price history
            high_history: High price history
            low_history: Low price history
            close_history: Close price history
            window_history: Window size for ATR calculation
            min_history_length: Minimum history length required

        Returns:
            Average True Range value, or 0.0 if insufficient data
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
        """
        Calculate total portfolio value (cash + position value).

        Args:
            current_position: Current position size (shares/units)
            current_price: Current market price per share/unit
            available_cash: Available cash

        Returns:
            Total portfolio value
        """
        position_value = current_position * current_price
        return available_cash + position_value

    @staticmethod
    def get_portfolio_return(
        current_position: float,
        current_price: float,
        available_cash: float,
        initial_capital: float,
    ) -> float:
        """
        Calculate portfolio return relative to initial capital.

        Args:
            current_position: Current position size (shares/units)
            current_price: Current market price per share/unit
            available_cash: Available cash
            initial_capital: Initial capital invested

        Returns:
            Portfolio return as a decimal (e.g., 0.05 for 5% return), or 0.0 if initial_capital is 0
        """
        if initial_capital == 0:
            return 0.0

        current_value = TradingStrategy.get_portfolio_value(
            current_position, current_price, available_cash
        )
        return (current_value - initial_capital) / initial_capital
