"""
Core infrastructure for Trading Strategies API

Provides configuration, security, exceptions, and rate limiting.
"""

from .config import settings, TradingSettings
from .security import get_api_key, security_scheme, create_api_key_header
from .exceptions import (
    TradingException,
    InvalidStrategyError,
    InsufficientCapitalError,
    InvalidParametersError,
    StrategyStoppedError,
)
from .rate_limit import limiter, rate_limit_exceeded_handler, get_rate_limit

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
