"""
Pydantic Schemas for Trading Strategies API

Defines request and response models for all trading strategy endpoints with
comprehensive validation and documentation.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Dict, List, Optional, Union, Any
from enum import Enum


# ========== ENUM CLASSES ==========


class StrategyTypeEnum(str, Enum):
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


# ========== BASE SCHEMAS ==========


class BaseStrategyRequest(BaseModel):
    """
    Base schema for all strategy requests.

    Contains common fields required by all trading strategies.
    """

    strategy_type: StrategyTypeEnum = Field(
        ..., description="Type of trading strategy to execute"
    )
    forecast_price: float = Field(
        ..., gt=0, description="Forecasted price (must be positive)"
    )
    current_price: float = Field(
        ..., gt=0, description="Current market price (must be positive)"
    )
    current_position: float = Field(
        ...,
        ge=0,
        description="Current position size in shares/units (must be non-negative, long-only)",
    )
    available_cash: float = Field(
        ..., ge=0, description="Available cash for trading (must be non-negative)"
    )
    initial_capital: float = Field(
        ..., gt=0, description="Initial capital invested (must be positive)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "strategy_type": "threshold",
                "forecast_price": 105.0,
                "current_price": 100.0,
                "current_position": 0.0,
                "available_cash": 100000.0,
                "initial_capital": 100000.0,
            }
        }


# ========== THRESHOLD STRATEGY SCHEMA ==========


class ThresholdStrategyRequest(BaseStrategyRequest):
    """
    Schema for threshold-based trading strategy.

    Threshold strategy compares forecast price to current price and generates
    buy/sell signals when the price difference exceeds a configurable threshold.
    """

    strategy_type: Literal["threshold"] = "threshold"
    threshold_type: Literal["absolute", "percentage", "std_dev", "atr"] = Field(
        ..., description="Type of threshold calculation"
    )
    threshold_value: float = Field(
        default=0.0,
        ge=0,
        description="Threshold value or multiplier (must be non-negative)",
    )
    execution_size: float = Field(
        default=1.0, gt=0, description="Position size to execute (must be positive)"
    )

    # Conditional fields for std_dev and atr
    which_history: Optional[Literal["open", "high", "low", "close"]] = Field(
        default="close",
        description="History type to use for std_dev threshold calculations",
    )
    window_history: Optional[int] = Field(
        default=20,
        gt=0,
        description="Window size for std_dev/atr calculations (must be positive)",
    )
    min_history_length: Optional[int] = Field(
        default=2,
        gt=0,
        description="Minimum history length required (must be positive)",
    )

    # OHLC data (required for atr, optional for std_dev)
    open_history: Optional[List[float]] = Field(
        default=None, description="Open price history (required for ATR threshold type)"
    )
    high_history: Optional[List[float]] = Field(
        default=None, description="High price history (required for ATR threshold type)"
    )
    low_history: Optional[List[float]] = Field(
        default=None, description="Low price history (required for ATR threshold type)"
    )
    close_history: Optional[List[float]] = Field(
        default=None,
        description="Close price history (required for ATR threshold type, optional for std_dev)",
    )

    @model_validator(mode="after")
    def validate_atr_requirements(self):
        """Validate that OHLC data is provided when threshold_type is 'atr'."""
        if self.threshold_type == "atr":
            if (
                self.open_history is None
                or self.high_history is None
                or self.low_history is None
                or self.close_history is None
            ):
                raise ValueError(
                    "All OHLC histories (open_history, high_history, low_history, close_history) "
                    "are required when threshold_type is 'atr'"
                )
        return self

    @field_validator("open_history", "high_history", "low_history", "close_history")
    @classmethod
    def validate_history_lengths(cls, v, info):
        """Validate that history arrays have reasonable lengths."""
        if v is not None and len(v) == 0:
            raise ValueError("History arrays cannot be empty")
        if v is not None and len(v) > 10000:
            raise ValueError("History arrays cannot exceed 10,000 elements")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "strategy_type": "threshold",
                "forecast_price": 105.0,
                "current_price": 100.0,
                "current_position": 0.0,
                "available_cash": 100000.0,
                "initial_capital": 100000.0,
                "threshold_type": "absolute",
                "threshold_value": 0.0,
                "execution_size": 100.0,
            }
        }


# ========== RETURN STRATEGY SCHEMA ==========


class ReturnStrategyRequest(BaseStrategyRequest):
    """
    Schema for return-based trading strategy.

    Return strategy generates buy/sell signals based on expected return relative
    to a threshold. Supports multiple position sizing methods.
    """

    strategy_type: Literal["return"] = "return"
    position_sizing: Literal["fixed", "proportional", "normalized"] = Field(
        ..., description="Position sizing method"
    )
    threshold_value: float = Field(
        ...,
        ge=0,
        description="Return threshold (e.g., 0.05 for 5%, must be non-negative)",
    )
    execution_size: float = Field(
        default=1.0, gt=0, description="Base execution size (must be positive)"
    )
    max_position_size: Optional[float] = Field(
        default=None,
        gt=0,
        description="Maximum position size constraint (optional, must be positive if provided)",
    )
    min_position_size: Optional[float] = Field(
        default=None,
        gt=0,
        description="Minimum position size constraint (optional, must be positive if provided)",
    )

    # Conditional for normalized sizing
    which_history: Optional[Literal["open", "high", "low", "close"]] = Field(
        default="close",
        description="History type to use for normalized position sizing",
    )
    window_history: Optional[int] = Field(
        default=20,
        gt=0,
        description="Window size for normalized sizing calculations (must be positive)",
    )
    min_history_length: Optional[int] = Field(
        default=2,
        gt=0,
        description="Minimum history length required (must be positive)",
    )
    open_history: Optional[List[float]] = None
    high_history: Optional[List[float]] = None
    low_history: Optional[List[float]] = None
    close_history: Optional[List[float]] = None

    @model_validator(mode="after")
    def validate_position_size_constraints(self):
        """Validate that max_position_size >= min_position_size if both provided."""
        if (
            self.max_position_size is not None
            and self.min_position_size is not None
            and self.max_position_size < self.min_position_size
        ):
            raise ValueError(
                "max_position_size must be >= min_position_size when both are provided"
            )
        return self

    @model_validator(mode="after")
    def validate_normalized_requirements(self):
        """Validate that history is provided when position_sizing is 'normalized'."""
        if self.position_sizing == "normalized":
            which_history = self.which_history or "close"
            history_field = f"{which_history}_history"
            history_value = getattr(self, history_field, None)
            if history_value is None or len(history_value) == 0:
                raise ValueError(
                    f"History data ({history_field}) is required when position_sizing is 'normalized'"
                )
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "strategy_type": "return",
                "forecast_price": 108.0,
                "current_price": 100.0,
                "current_position": 100.0,
                "available_cash": 90000.0,
                "initial_capital": 100000.0,
                "position_sizing": "proportional",
                "threshold_value": 0.05,
                "execution_size": 10.0,
                "max_position_size": 150.0,
                "min_position_size": 5.0,
            }
        }


# ========== QUANTILE STRATEGY SCHEMA ==========


class QuantileSignalConfig(BaseModel):
    """
    Configuration for a single quantile signal.

    Defines a signal action (buy/sell/hold) for a specific percentile range.
    """

    range: List[float] = Field(
        ...,
        min_items=2,
        max_items=2,
        description="Percentile range [min, max] where 0 <= min < max <= 100",
    )
    signal: Literal["buy", "sell", "hold"] = Field(
        ..., description="Signal action for this percentile range"
    )
    multiplier: float = Field(
        ..., ge=0, le=1, description="Multiplier for position sizing (0.0 to 1.0)"
    )

    @field_validator("range")
    @classmethod
    def validate_range(cls, v):
        """Validate percentile range."""
        if len(v) != 2:
            raise ValueError("Range must have exactly 2 elements [min, max]")
        min_val, max_val = v[0], v[1]
        if min_val < 0 or max_val > 100:
            raise ValueError("Range values must be between 0 and 100")
        if min_val >= max_val:
            raise ValueError("Range min must be < max")
        return v

    class Config:
        json_schema_extra = {
            "example": {"range": [90, 95], "signal": "buy", "multiplier": 0.75}
        }


class QuantileStrategyRequest(BaseStrategyRequest):
    """
    Schema for quantile-based trading strategy.

    Quantile strategy calculates the percentile of forecast price relative to
    historical distribution and generates signals based on quantile ranges.
    """

    strategy_type: Literal["quantile"] = "quantile"
    which_history: Literal["open", "high", "low", "close"] = Field(
        ..., description="History type to use for quantile calculation"
    )
    window_history: int = Field(
        ..., gt=0, description="Window size for quantile calculation (must be positive)"
    )
    quantile_signals: Dict[int, QuantileSignalConfig] = Field(
        ..., description="Quantile signal configuration dictionary"
    )
    position_sizing: Optional[Literal["fixed", "normalized"]] = Field(
        default="fixed", description="Position sizing method (default: fixed)"
    )
    execution_size: float = Field(
        default=1.0, gt=0, description="Base execution size (must be positive)"
    )
    max_position_size: Optional[float] = Field(
        default=None, gt=0, description="Maximum position size constraint (optional)"
    )
    min_position_size: Optional[float] = Field(
        default=None, gt=0, description="Minimum position size constraint (optional)"
    )
    min_history_length: Optional[int] = Field(
        default=2,
        gt=0,
        description="Minimum history length required (must be positive)",
    )

    # OHLC data (required)
    open_history: List[float] = Field(..., description="Open price history (required)")
    high_history: List[float] = Field(..., description="High price history (required)")
    low_history: List[float] = Field(..., description="Low price history (required)")
    close_history: List[float] = Field(
        ..., description="Close price history (required)"
    )

    @model_validator(mode="after")
    def validate_ohlc_lengths(self):
        """Validate that all OHLC arrays have matching lengths."""
        ohlc_arrays = [
            self.open_history,
            self.high_history,
            self.low_history,
            self.close_history,
        ]
        lengths = [len(arr) for arr in ohlc_arrays]
        if len(set(lengths)) > 1:
            raise ValueError(
                f"All OHLC history arrays must have the same length. "
                f"Found lengths: open={lengths[0]}, high={lengths[1]}, low={lengths[2]}, close={lengths[3]}"
            )
        return self

    @model_validator(mode="after")
    def validate_position_size_constraints(self):
        """Validate that max_position_size >= min_position_size if both provided."""
        if (
            self.max_position_size is not None
            and self.min_position_size is not None
            and self.max_position_size < self.min_position_size
        ):
            raise ValueError(
                "max_position_size must be >= min_position_size when both are provided"
            )
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "strategy_type": "quantile",
                "forecast_price": 110.0,
                "current_price": 100.0,
                "current_position": 100.0,
                "available_cash": 90000.0,
                "initial_capital": 100000.0,
                "which_history": "close",
                "window_history": 20,
                "quantile_signals": {
                    1: {"range": [0, 5], "signal": "sell", "multiplier": 1.0},
                    2: {"range": [90, 95], "signal": "buy", "multiplier": 0.75},
                },
                "position_sizing": "fixed",
                "execution_size": 100.0,
                "open_history": [95.2, 96.1, 97.5],
                "high_history": [105.3, 106.2, 107.8],
                "low_history": [94.1, 95.0, 96.2],
                "close_history": [100.5, 101.2, 102.8],
            }
        }


# ========== DISCRIMINATED UNION ==========

# Union type for request routing (discriminated by strategy_type)
StrategyRequest = Union[
    ThresholdStrategyRequest, ReturnStrategyRequest, QuantileStrategyRequest
]


# ========== RESPONSE SCHEMAS ==========


class StrategyResponse(BaseModel):
    """
    Response schema for strategy execution.

    Contains the execution result with action, size, value, and updated state.
    """

    action: Literal["buy", "sell", "hold"] = Field(
        ..., description="Trading action: buy, sell, or hold"
    )
    size: float = Field(
        ..., ge=0, description="Position size executed (shares/units, non-negative)"
    )
    value: float = Field(..., ge=0, description="Dollar value of trade (non-negative)")
    reason: str = Field(..., description="Explanation of the action taken")
    available_cash: float = Field(
        ..., ge=0, description="Available cash after trade (non-negative)"
    )
    position_after: float = Field(
        ..., ge=0, description="Position size after trade (non-negative)"
    )
    stopped: bool = Field(
        ..., description="Whether strategy is stopped (no capital remaining)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "action": "buy",
                "size": 100.0,
                "value": 10000.0,
                "reason": "Forecast 105.00 > Price 100.00, magnitude 5.0000 > threshold 0.0000",
                "available_cash": 90000.0,
                "position_after": 100.0,
                "stopped": False,
            }
        }


class StrategyInfo(BaseModel):
    """
    Information about a single trading strategy.

    Used in the strategies list endpoint.
    """

    type: str = Field(..., description="Strategy type identifier")
    description: str = Field(..., description="Strategy description")
    parameters: Dict[str, Any] = Field(..., description="Parameter requirements")


class StrategyListResponse(BaseModel):
    """
    Response schema for listing available strategies.

    Contains information about all supported trading strategies.
    """

    strategies: List[StrategyInfo] = Field(
        ..., description="List of available trading strategies"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "strategies": [
                    {
                        "type": "threshold",
                        "description": "Threshold-based strategy with configurable threshold types",
                        "parameters": {
                            "required": [
                                "forecast_price",
                                "current_price",
                                "threshold_type",
                                "threshold_value",
                            ],
                            "optional": [
                                "execution_size",
                                "which_history",
                                "window_history",
                            ],
                        },
                    }
                ]
            }
        }
