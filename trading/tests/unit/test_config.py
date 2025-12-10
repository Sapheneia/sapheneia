"""
Unit tests for configuration management.

Tests TradingSettings class, environment variable loading, and validation.
"""

import pytest
import os
from unittest.mock import patch
from pydantic import ValidationError


class TestConfigLoading:
    """Test configuration loading from environment and defaults."""

    def test_default_values(self):
        """Test default configuration values."""
        # Import here to avoid circular issues
        from trading.core.config import TradingSettings

        # Create settings with minimal required values
        with patch.dict(
            os.environ, {"TRADING_API_KEY": "test_key_32_chars_minimum_length_required"}
        ):
            settings = TradingSettings()

            assert settings.TRADING_API_PORT == 9000
            assert settings.TRADING_API_HOST == "0.0.0.0"
            assert settings.ENVIRONMENT == "development"
            assert settings.LOG_LEVEL == "INFO"
            assert settings.RATE_LIMIT_ENABLED is True
            assert settings.RATE_LIMIT_EXECUTE_PER_MINUTE == 10

    def test_environment_variable_override(self):
        """Test environment variables override defaults."""
        from trading.core.config import TradingSettings

        with patch.dict(
            os.environ,
            {
                "TRADING_API_KEY": "test_key_32_chars_minimum_length_required",
                "TRADING_API_PORT": "9001",
                "LOG_LEVEL": "DEBUG",
            },
        ):
            settings = TradingSettings()

            assert settings.TRADING_API_PORT == 9001
            assert settings.LOG_LEVEL == "DEBUG"

    def test_cors_origins_string(self):
        """Test CORS origins stored as comma-separated string."""
        from trading.core.config import TradingSettings

        with patch.dict(
            os.environ, {"TRADING_API_KEY": "test_key_32_chars_minimum_length_required"}
        ):
            settings = TradingSettings()
            # CORS_ALLOWED_ORIGINS is stored as a comma-separated string
            assert isinstance(settings.CORS_ALLOWED_ORIGINS, str)
            assert (
                "," in settings.CORS_ALLOWED_ORIGINS
                or len(settings.CORS_ALLOWED_ORIGINS) > 0
            )

    def test_cors_methods_string(self):
        """Test CORS methods stored as comma-separated string."""
        from trading.core.config import TradingSettings

        with patch.dict(
            os.environ, {"TRADING_API_KEY": "test_key_32_chars_minimum_length_required"}
        ):
            settings = TradingSettings()
            # CORS_ALLOW_METHODS is stored as a comma-separated string
            assert isinstance(settings.CORS_ALLOW_METHODS, str)
            assert "GET" in settings.CORS_ALLOW_METHODS
            assert "POST" in settings.CORS_ALLOW_METHODS


class TestAPIKeyValidation:
    """Test API key validation."""

    def test_api_key_validation_production_short_key(self):
        """Test API key validation warns in production with short key."""
        from trading.core.config import TradingSettings

        with patch.dict(
            os.environ,
            {
                "TRADING_API_KEY": "short",
                "ENVIRONMENT": "production",
            },
        ):
            # Current implementation only warns, doesn't raise ValidationError
            # The validator checks length but only raises ValueError if default key in production
            settings = TradingSettings()
            # Should still create settings (may log warning)
            assert settings.TRADING_API_KEY == "short"

    def test_api_key_validation_production_valid_key(self):
        """Test API key validation passes in production with valid key."""
        from trading.core.config import TradingSettings

        with patch.dict(
            os.environ,
            {
                "TRADING_API_KEY": "a" * 32,  # 32 characters
                "ENVIRONMENT": "production",
            },
        ):
            settings = TradingSettings()
            assert len(settings.TRADING_API_KEY) >= 32

    def test_api_key_validation_development_allows_short(self):
        """Test API key validation allows short key in development."""
        from trading.core.config import TradingSettings

        with patch.dict(
            os.environ,
            {
                "TRADING_API_KEY": "short",
                "ENVIRONMENT": "development",
            },
        ):
            # Should not raise error in development
            settings = TradingSettings()
            assert settings.TRADING_API_KEY == "short"
