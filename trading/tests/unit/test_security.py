"""
Unit tests for security and authentication.

Tests API key validation and authentication mechanisms.
"""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from trading.core.security import get_api_key, security_scheme
from trading.core.config import settings


class TestAPIKeyAuthentication:
    """Test API key authentication."""

    @pytest.mark.asyncio
    async def test_valid_api_key(self):
        """Test valid API key is accepted."""
        # Create mock credentials with valid API key
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=settings.TRADING_API_KEY
        )

        # Should not raise exception
        result = await get_api_key(credentials)
        assert result == settings.TRADING_API_KEY

    @pytest.mark.asyncio
    async def test_invalid_api_key(self):
        """Test invalid API key is rejected."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid_key"
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_api_key(credentials)

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_wrong_api_key(self):
        """Test wrong API key is rejected."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="wrong_api_key_that_does_not_match"
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_api_key(credentials)

        assert exc_info.value.status_code == 401
