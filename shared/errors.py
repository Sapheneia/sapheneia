"""
Shared Error Hierarchy for Sapheneia Services.

Provides a unified error system that all services (metrics, orchestration,
trading, forecast) can use for structured error responses.

The interface mirrors forecast's SapheneiaException pattern:
- message, error_code, details, suggested_status_code, to_dict()

Usage:
    from shared.errors import ValidationError, register_error_handlers

    # In service code
    raise ValidationError("Returns series is empty", details={"field": "returns"})

    # In main.py
    register_error_handlers(app)
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Machine-readable error codes for structured error responses."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_MODEL = "INVALID_MODEL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    COMPUTATION_ERROR = "COMPUTATION_ERROR"
    TIMEOUT = "TIMEOUT"


class SapheneiaError(Exception):
    """
    Base exception for shared Sapheneia error handling.

    Provides structured error information with:
    - error_code: Machine-readable error code
    - message: Human-readable error message
    - details: Additional context for debugging
    - suggested_status_code: Suggested HTTP status code
    """

    def __init__(
        self,
        message: str,
        error_code: str = "SAPHENEIA_ERROR",
        details: Optional[Dict[str, Any]] = None,
        suggested_status_code: int = 500,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggested_status_code = suggested_status_code
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format for JSON responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(SapheneiaError):
    """Input validation failed (bad format, missing fields, out of range)."""

    def __init__(
        self,
        message: str = "Validation error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=details,
            suggested_status_code=400,
        )


class ModelUnavailableError(SapheneiaError):
    """Model backend returned 5xx or is not responding (retryable)."""

    def __init__(
        self,
        message: str = "Model unavailable",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.MODEL_UNAVAILABLE,
            details=details,
            suggested_status_code=503,
        )


class ServiceUnavailableError(SapheneiaError):
    """Downstream service is unreachable (connection refused, DNS failure)."""

    def __init__(
        self,
        message: str = "Service unavailable",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            details=details,
            suggested_status_code=503,
        )


class ServiceTimeoutError(SapheneiaError):
    """Downstream service timed out."""

    def __init__(
        self,
        message: str = "Service timeout",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT,
            details=details,
            suggested_status_code=504,
        )


class InsufficientDataError(SapheneiaError):
    """Not enough data points to perform the requested computation."""

    def __init__(
        self,
        message: str = "Insufficient data",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.INSUFFICIENT_DATA,
            details=details,
            suggested_status_code=400,
        )


class ComputationError(SapheneiaError):
    """A computation step failed (missing keys, empty results, math errors)."""

    def __init__(
        self,
        message: str = "Computation error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.COMPUTATION_ERROR,
            details=details,
            suggested_status_code=500,
        )


def register_error_handlers(app) -> None:
    """
    Register SapheneiaError and generic Exception handlers on a FastAPI app.

    Provides consistent structured JSON error responses with request_id.

    Args:
        app: FastAPI application instance
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(SapheneiaError)
    async def sapheneia_error_handler(request: Request, exc: SapheneiaError) -> JSONResponse:
        request_id = getattr(getattr(request, "state", None), "request_id", "unknown")
        logger.error(f"[{request_id}] SapheneiaError: {exc.error_code} - {exc.message}")
        if exc.details:
            logger.error(f"[{request_id}]   Details: {exc.details}")

        error_dict = exc.to_dict()
        error_dict["details"]["request_id"] = request_id

        response = JSONResponse(
            status_code=exc.suggested_status_code,
            content=error_dict,
        )
        if hasattr(getattr(request, "state", None), "request_id"):
            response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(getattr(request, "state", None), "request_id", "unknown")
        logger.exception(f"[{request_id}] Unexpected error occurred")

        response = JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please contact support.",
                "details": {
                    "error_type": type(exc).__name__,
                    "request_id": request_id,
                },
            },
        )
        if hasattr(getattr(request, "state", None), "request_id"):
            response.headers["X-Request-ID"] = request.state.request_id
        return response
