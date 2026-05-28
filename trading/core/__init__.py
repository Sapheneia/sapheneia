"""
Core infrastructure for Trading Strategies API

Provides configuration, security, exceptions, and rate limiting.
"""

from .config import TradingSettings, settings
from .exceptions import (
    InsufficientCapitalError,
    InvalidParametersError,
    InvalidStrategyError,
    StrategyStoppedError,
    TradingException,
)
from .rate_limit import get_rate_limit, limiter, rate_limit_exceeded_handler
from .security import create_api_key_header, get_api_key, security_scheme

__all__ = [
    "settings",
    "TradingSettings",
    "get_api_key",
    "security_scheme",
    "create_api_key_header",
    "TradingException",
    "InvalidStrategyError",
    "InsufficientCapitalError",
    "InvalidParametersError",
    "StrategyStoppedError",
    "limiter",
    "rate_limit_exceeded_handler",
    "get_rate_limit",
]
