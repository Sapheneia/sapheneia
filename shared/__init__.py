"""
Shared utilities for Sapheneia services.
"""

from .errors import (
    SapheneiaError,
    ValidationError,
    ModelUnavailableError,
    ServiceUnavailableError,
    ServiceTimeoutError,
    InsufficientDataError,
    ComputationError,
    ErrorCode,
    register_error_handlers,
)

__all__ = [
    "SapheneiaError",
    "ValidationError",
    "ModelUnavailableError",
    "ServiceUnavailableError",
    "ServiceTimeoutError",
    "InsufficientDataError",
    "ComputationError",
    "ErrorCode",
    "register_error_handlers",
]
