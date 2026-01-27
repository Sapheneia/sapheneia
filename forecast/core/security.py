"""
API Security and Authentication

Implements API key authentication using the Authorization header.
Supports both "Bearer" and "Api-Key" authorization schemes.
"""

from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from .config import settings

logger = logging.getLogger(__name__)

# Security scheme for API key authentication
security_scheme = HTTPBearer()


async def get_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme)
) -> str:
    """
    Dependency function to validate API key from Authorization header.

    Supports two formats:
    - Authorization: Bearer YOUR_API_KEY
    - Authorization: Api-Key YOUR_API_KEY

    Args:
        credentials: HTTP authorization credentials from request header

    Returns:
        The validated API key

    Raises:
        HTTPException: 401 if API key is invalid or missing
    """
    provided_key = credentials.credentials

    # Enhanced logging for debugging authentication issues
    logger.info(f"🔐 Authentication attempt:")
    logger.info(f"   Scheme: {credentials.scheme}")
    logger.info(f"   Provided key (first 8 chars): {provided_key[:8] if provided_key else 'NONE'}...")
    logger.info(f"   Expected key (first 8 chars): {settings.API_SECRET_KEY[:8]}...")
    logger.info(f"   Keys match: {provided_key == settings.API_SECRET_KEY}")

    # Validate against configured API key
    if provided_key != settings.API_SECRET_KEY:
        logger.error(f"❌ Authentication FAILED:")
        logger.error(f"   Provided: {provided_key[:min(20, len(provided_key))] if provided_key else 'NONE'}...")
        logger.error(f"   Expected: {settings.API_SECRET_KEY[:min(20, len(settings.API_SECRET_KEY))]}...")
        logger.error(f"   Provided length: {len(provided_key) if provided_key else 0}")
        logger.error(f"   Expected length: {len(settings.API_SECRET_KEY)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("✅ API key validated successfully")
    return provided_key


def create_api_key_header(api_key: str) -> dict:
    """
    Helper function to create Authorization header for API requests.

    Args:
        api_key: The API key to use

    Returns:
        Dictionary with Authorization header
    """
    return {"Authorization": f"Bearer {api_key}"}
