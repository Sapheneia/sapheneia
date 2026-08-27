"""
Shared utilities for Sapheneia services.
"""

from .contracts import ForecastEnvelope, ForecastRequest, ModelMismatchError, QuantileBand
from .errors import (
    ComputationError,
    ErrorCode,
    InsufficientDataError,
    ModelUnavailableError,
    SapheneiaError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    ValidationError,
    register_error_handlers,
)
from .model_family import ModelFamily

# NOTE: ``shared.http_client`` is deliberately NOT re-exported here — importing it
# would pull ``httpx`` into every service image, including leaf services that make
# no outbound calls. Callers import ``shared.http_client`` directly.

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
    "ForecastEnvelope",
    "ForecastRequest",
    "QuantileBand",
    "ModelMismatchError",
    "ModelFamily",
]
