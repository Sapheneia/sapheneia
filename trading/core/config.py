"""
Configuration Management for Trading Strategies API

Uses Pydantic Settings to manage configuration from environment variables
and .env files. Supports both local development and production deployments.
"""

import logging
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.service_config import validate_api_key


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
    # ENVIRONMENT MUST be declared before TRADING_API_KEY. Pydantic validates
    # fields in declaration order and exposes only already-validated fields via
    # `info.data`, so with the reverse order the key validator always read the
    # "development" fallback and the production guard never fired — including
    # when ENVIRONMENT=production was explicitly set.
    ENVIRONMENT: str = "development"  # Can be: development, staging, production
    TRADING_API_KEY: str = (
        "default_trading_api_key_please_change"  # MUST be set in .env or environment
    )
    LOG_LEVEL: str = "INFO"
    TRADING_API_PORT: int = 9000  # Default port for Trading API (separate from api/ on 8000+)
    TRADING_API_HOST: str = "0.0.0.0"  # Listen on all interfaces, crucial for Docker

    # --- CORS Settings ---
    CORS_ALLOWED_ORIGINS: str = (
        "http://localhost:8080,http://localhost:3000"  # Comma-separated list
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST"
    CORS_ALLOW_HEADERS: str = "*"

    # --- Rate Limiting Settings ---
    # Rate limits below are per-client-IP and exist to bound abuse on the
    # published host port. They are NOT the concurrency control for the
    # orchestrator: it drives one call per backtest iteration (one per
    # trading day), so a 10/minute cap made any real backtest impossible —
    # every run died partway through with a 429. Real concurrency is
    # bounded by the orchestrator's global and per-model semaphores.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 600
    RATE_LIMIT_EXECUTE_PER_MINUTE: int = 6000  # ~100/s; one call per backtest iteration
    RATE_LIMIT_STORAGE_URI: str = "memory://"  # Can be "redis://localhost:6379" for distributed

    # --- Trading Strategy Defaults ---
    DEFAULT_MIN_HISTORY_LENGTH: int = 2  # Minimum history length required
    DEFAULT_EXECUTION_SIZE: float = 1.0  # Default execution size

    # --- Performance Monitoring Settings ---
    SLOW_REQUEST_THRESHOLD_MS: int = 100  # Threshold for slow request logging (milliseconds)

    # --- Trading Strategy Constants ---
    MAX_HISTORY_WINDOW: int = 10000  # Maximum window size for history calculations
    DEFAULT_WINDOW_SIZE: int = 20  # Default window size for calculations
    MAX_ARRAY_SIZE: int = 10000  # Maximum size for history arrays

    @field_validator("TRADING_API_KEY")
    @classmethod
    def validate_api_key(cls, v: str, info) -> str:
        """Refuse to boot in production with a placeholder or short key.

        The implementation lives in ``shared.service_config`` so the same guard
        applies to the orchestrator, data, and metrics services — it used to
        exist only here (CLAUDE.md §5.4).
        """
        return validate_api_key(
            v,
            environment=info.data.get("ENVIRONMENT", "development"),
            field_name="TRADING_API_KEY",
        )

    def get_cors_origins(self) -> list[str]:
        """
        Convert comma-separated CORS origins string to list.

        Returns:
            List of allowed CORS origins
        """
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    def get_cors_methods(self) -> list[str]:
        """
        Convert comma-separated CORS methods string to list.

        Returns:
            List of allowed CORS methods
        """
        return [method.strip() for method in self.CORS_ALLOW_METHODS.split(",") if method.strip()]


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
logger.info(f"Rate Limiting: {'enabled' if settings.RATE_LIMIT_ENABLED else 'disabled'}")
logger.info(f"Execute Endpoint Limit: {settings.RATE_LIMIT_EXECUTE_PER_MINUTE}/minute")
logger.info("=" * 80)
