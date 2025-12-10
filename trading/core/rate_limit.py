"""
Rate Limiting for Trading Strategies API

Provides request rate limiting using slowapi to prevent abuse and ensure
fair resource allocation.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import logging

from .config import settings

logger = logging.getLogger(__name__)


# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    enabled=settings.RATE_LIMIT_ENABLED,
    headers_enabled=True,  # Add rate limit headers to responses
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom handler for rate limit exceeded errors.

    Args:
        request: The incoming request
        exc: The rate limit exception

    Returns:
        JSON response with 429 status code
    """
    logger.warning(
        f"Rate limit exceeded for {get_remote_address(request)} "
        f"on path {request.url.path}"
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "detail": str(exc.detail) if hasattr(exc, "detail") else None,
        },
        headers=getattr(exc, "headers", {}),
    )


# Predefined rate limit strings for common use cases
RATE_LIMITS = {
    "default": f"{settings.RATE_LIMIT_PER_MINUTE}/minute",
    "execute": f"{settings.RATE_LIMIT_EXECUTE_PER_MINUTE}/minute",
    "health": "30/minute",  # Health checks can be more frequent
    "strategies": "30/minute",  # Strategy list endpoint
}


def get_rate_limit(limit_type: str = "default") -> str:
    """
    Get rate limit string for a specific limit type.

    Args:
        limit_type: Type of rate limit (default, execute, health, strategies)

    Returns:
        Rate limit string in format "X/period"
    """
    return RATE_LIMITS.get(limit_type, RATE_LIMITS["default"])
