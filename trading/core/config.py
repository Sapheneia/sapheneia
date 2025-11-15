"""
Configuration Management for Trading Strategies API

Uses Pydantic Settings to manage configuration from environment variables
and .env files. Supports both local development and production deployments.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import os
import logging
from typing import List


class TradingSettings(BaseSettings):
    """
    Manages trading API settings using Pydantic, reading from environment variables
    and optionally a .env file for local development.
    """

    # Configuration to load .env file (useful locally, ignored in Docker if not present)
    # Assumes .env is in the project root ('sapheneia/') relative to where script runs
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra variables not defined in the model
    )

    # --- Core API Settings ---
    TRADING_API_KEY: str = (
        "default_trading_api_key_please_change"  # MUST be set in .env or environment
    )
    LOG_LEVEL: str = "INFO"
    TRADING_API_PORT: int = (
        9000  # Default port for Trading API (separate from api/ on 8000+)
    )
    TRADING_API_HOST: str = "0.0.0.0"  # Listen on all interfaces, crucial for Docker
    ENVIRONMENT: str = "development"  # Can be: development, staging, production

    # --- CORS Settings ---
    CORS_ALLOWED_ORIGINS: str = (
        "http://localhost:8080,http://localhost:3000"  # Comma-separated list
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST"
    CORS_ALLOW_HEADERS: str = "*"

    # --- Rate Limiting Settings ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60  # Default: 60 requests per minute
    RATE_LIMIT_EXECUTE_PER_MINUTE: int = 10  # Stricter limit for execute endpoint
    RATE_LIMIT_STORAGE_URI: str = (
        "memory://"  # Can be "redis://localhost:6379" for distributed
    )

    # --- Trading Strategy Defaults ---
    DEFAULT_MIN_HISTORY_LENGTH: int = 2  # Minimum history length required
    DEFAULT_EXECUTION_SIZE: float = 1.0  # Default execution size

    # --- Performance Monitoring Settings ---
    SLOW_REQUEST_THRESHOLD_MS: int = (
        100  # Threshold for slow request logging (milliseconds)
    )

    # --- Trading Strategy Constants ---
    MAX_HISTORY_WINDOW: int = 10000  # Maximum window size for history calculations
    DEFAULT_WINDOW_SIZE: int = 20  # Default window size for calculations
    MAX_ARRAY_SIZE: int = 10000  # Maximum size for history arrays

    @field_validator("TRADING_API_KEY")
    @classmethod
    def validate_api_key(cls, v: str, info) -> str:
        """
        Validate that TRADING_API_KEY is changed from default in production.

        Args:
            v: The API key value
            info: Validation info containing other field values

        Returns:
            The validated API key

        Raises:
            ValueError: If default key is used in production environment
        """
        environment = info.data.get("ENVIRONMENT", "development")

        if v == "default_trading_api_key_please_change":
            if environment == "production":
                raise ValueError(
                    "❌ CRITICAL SECURITY ERROR: TRADING_API_KEY must be changed from default value in production! "
                    "Set TRADING_API_KEY in your .env file or environment variables."
                )
            else:
                # Log warning but allow in development/staging
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    "⚠️  WARNING: Using default TRADING_API_KEY! This is NOT secure for production."
                )

        # Validate minimum length
        if len(v) < 32:
            if environment == "production":
                raise ValueError(
                    "❌ SECURITY ERROR: TRADING_API_KEY must be at least 32 characters long in production."
                )
            else:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"⚠️  WARNING: TRADING_API_KEY is only {len(v)} characters. Recommended: 32+ characters."
                )

        return v

    def get_cors_origins(self) -> List[str]:
        """
        Convert comma-separated CORS origins string to list.

        Returns:
            List of allowed CORS origins
        """
        return [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    def get_cors_methods(self) -> List[str]:
        """
        Convert comma-separated CORS methods string to list.

        Returns:
            List of allowed CORS methods
        """
        return [
            method.strip()
            for method in self.CORS_ALLOW_METHODS.split(",")
            if method.strip()
        ]


# Instantiate settings early to make them available for import
settings = TradingSettings()

# --- Configure Root Logger ---
# Basic configuration, customize further if needed (e.g., file logging)
log_level_numeric = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level_numeric,
    format="%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s",  # Wider name field
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Optional: Adjust log levels for noisy libraries
logging.getLogger("uvicorn.access").setLevel(max(log_level_numeric, logging.WARNING))
logging.getLogger("urllib3").setLevel(max(log_level_numeric, logging.INFO))

logger = logging.getLogger(__name__)  # Logger for this config module
logger.info("=" * 80)
logger.info("Trading Strategies API Configuration")
logger.info("=" * 80)
logger.info(f"Log Level: {settings.LOG_LEVEL}")
logger.info(f"API Host:Port: {settings.TRADING_API_HOST}:{settings.TRADING_API_PORT}")
logger.info(f"Environment: {settings.ENVIRONMENT}")
logger.info(
    f"Rate Limiting: {'enabled' if settings.RATE_LIMIT_ENABLED else 'disabled'}"
)
logger.info(f"Execute Endpoint Limit: {settings.RATE_LIMIT_EXECUTE_PER_MINUTE}/minute")
logger.info("=" * 80)
