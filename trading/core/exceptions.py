"""
Custom Exception Hierarchy for Trading Strategies API.

Provides structured error handling with consistent error codes and messages.
Allows for better error tracking, debugging, and user-friendly error responses.

Usage:
    # In service code
    raise InsufficientCapitalError("Not enough cash to execute buy order", available_cash=1000.0, required=5000.0)

    # In endpoints - caught automatically by exception handlers
    # Returns structured JSON response with error_code, message, details
"""

from typing import Optional, Dict, Any


class TradingException(Exception):
    """
    Base exception for all Trading Strategies API errors.

    Provides structured error information with:
    - error_code: Machine-readable error code
    - message: Human-readable error message
    - details: Additional context for debugging
    - suggested_status_code: Suggested HTTP status code
    """

    def __init__(
        self,
        message: str,
        error_code: str = "TRADING_ERROR",
        details: Optional[Dict[str, Any]] = None,
        suggested_status_code: int = 500,
    ):
        """
        Initialize TradingException.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional context dictionary
            suggested_status_code: Suggested HTTP status code
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggested_status_code = suggested_status_code
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary format for JSON responses.

        Returns:
            Dictionary with error information
        """
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class InvalidStrategyError(TradingException):
    """
    Raised when an invalid strategy type is provided.

    Examples:
        - Unknown strategy_type value
        - Strategy type not supported
    """

    def __init__(
        self,
        message: str = "Invalid strategy type",
        strategy_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize InvalidStrategyError.

        Args:
            message: Error message
            strategy_type: The invalid strategy type that was provided
            details: Additional context
        """
        if details is None:
            details = {}
        if strategy_type:
            details["strategy_type"] = strategy_type
            details["valid_strategies"] = ["threshold", "return", "quantile"]
        super().__init__(
            message,
            error_code="INVALID_STRATEGY_ERROR",
            details=details,
            suggested_status_code=400,
        )


class InsufficientCapitalError(TradingException):
    """
    Raised when there is insufficient capital to execute a trade.

    Examples:
        - Not enough cash to buy requested position size
        - Position size exceeds available capital
    """

    def __init__(
        self,
        message: str = "Insufficient capital to execute trade",
        available_cash: Optional[float] = None,
        required: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize InsufficientCapitalError.

        Args:
            message: Error message
            available_cash: Available cash amount
            required: Required cash amount
            details: Additional context
        """
        if details is None:
            details = {}
        if available_cash is not None:
            details["available_cash"] = available_cash
        if required is not None:
            details["required"] = required
            if available_cash is not None:
                details["shortfall"] = required - available_cash
        super().__init__(
            message,
            error_code="INSUFFICIENT_CAPITAL_ERROR",
            details=details,
            suggested_status_code=400,
        )


class InvalidParametersError(TradingException):
    """
    Raised when invalid parameters are provided for a strategy.

    Examples:
        - Missing required parameters
        - Invalid parameter values (negative prices, etc.)
        - Parameter type mismatches
        - Invalid parameter combinations
    """

    def __init__(
        self,
        message: str = "Invalid parameters provided",
        parameter: Optional[str] = None,
        validation_errors: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize InvalidParametersError.

        Args:
            message: Error message
            parameter: The parameter that is invalid
            validation_errors: Dictionary of validation errors
            details: Additional context
        """
        if details is None:
            details = {}
        if parameter:
            details["parameter"] = parameter
        if validation_errors:
            details["validation_errors"] = validation_errors
        super().__init__(
            message,
            error_code="INVALID_PARAMETERS_ERROR",
            details=details,
            suggested_status_code=400,
        )


class StrategyStoppedError(TradingException):
    """
    Raised when a strategy is stopped (no capital remaining).

    This is a special case where the strategy cannot execute any trades
    because both available_cash and current_position are zero or negative.
    """

    def __init__(
        self,
        message: str = "Strategy stopped: no capital remaining",
        available_cash: Optional[float] = None,
        current_position: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize StrategyStoppedError.

        Args:
            message: Error message
            available_cash: Available cash amount
            current_position: Current position size
            details: Additional context
        """
        if details is None:
            details = {}
        if available_cash is not None:
            details["available_cash"] = available_cash
        if current_position is not None:
            details["current_position"] = current_position
        super().__init__(
            message,
            error_code="STRATEGY_STOPPED_ERROR",
            details=details,
            suggested_status_code=400,
        )
