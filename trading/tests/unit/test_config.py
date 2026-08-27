"""
Unit tests for configuration management.

Tests TradingSettings class, environment variable loading, and validation.
"""

import os
from unittest.mock import patch

import pytest


class TestConfigLoading:
    """Test configuration loading from environment and defaults."""

    def test_default_values(self):
        """Code defaults — isolated from both .env and the ambient environment.

        ``_env_file=None`` only ignores the .env *file*. Any of these names
        already exported in the developer's shell (e.g. after
        ``set -a; source .env``) would still win, so the test would assert
        against the shell's values rather than the code defaults it claims to
        check. They are cleared explicitly.
        """
        # Import here to avoid circular issues
        from trading.core.config import TradingSettings

        overridable = [
            name
            for name in os.environ
            if name.startswith(("TRADING_", "RATE_LIMIT_")) or name in {"ENVIRONMENT", "LOG_LEVEL"}
        ]
        with patch.dict(
            os.environ,
            {"TRADING_API_KEY": "test_key_32_chars_minimum_length_required"},
            clear=False,
        ):
            for name in overridable:
                os.environ.pop(name, None)
            os.environ["TRADING_API_KEY"] = "test_key_32_chars_minimum_length_required"
            settings = TradingSettings(_env_file=None)

            assert settings.TRADING_API_PORT == 9000
            assert settings.TRADING_API_HOST == "0.0.0.0"
            assert settings.ENVIRONMENT == "development"
            assert settings.LOG_LEVEL == "INFO"
            assert settings.RATE_LIMIT_ENABLED is True
            # Raised from 10: the orchestrator calls /execute once per backtest
            # iteration, so the old cap made any real run die partway with a 429.
            # See tests/test_rate_limit_budget.py for the workload floor.
            assert settings.RATE_LIMIT_EXECUTE_PER_MINUTE == 6000

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
            assert "," in settings.CORS_ALLOWED_ORIGINS or len(settings.CORS_ALLOWED_ORIGINS) > 0

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
        """A short key in production must refuse to boot.

        This previously asserted the opposite — that a 5-character key was
        accepted in production — which was true only because ``ENVIRONMENT``
        was declared *after* ``TRADING_API_KEY``. Pydantic exposes only
        already-validated fields through ``info.data``, so the validator always
        read the "development" fallback and the guard never fired.
        """
        import pydantic

        from trading.core.config import TradingSettings

        with (
            patch.dict(
                os.environ,
                {
                    "TRADING_API_KEY": "short",
                    "ENVIRONMENT": "production",
                },
            ),
            pytest.raises(pydantic.ValidationError, match="32\\+ is required in production"),
        ):
            TradingSettings(_env_file=None)

    def test_api_key_validation_production_default_key(self):
        """The shipped placeholder must refuse to boot in production."""
        import pydantic

        from trading.core.config import TradingSettings

        with (
            patch.dict(
                os.environ,
                {
                    "TRADING_API_KEY": "default_trading_api_key_please_change",
                    "ENVIRONMENT": "production",
                },
            ),
            pytest.raises(pydantic.ValidationError, match="placeholder"),
        ):
            TradingSettings(_env_file=None)

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
