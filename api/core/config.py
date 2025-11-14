"""
Configuration Management for Sapheneia API

Uses Pydantic Settings to manage configuration from environment variables
and .env files. Supports both local development and production deployments.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import os
import logging
from typing import Optional


class Settings(BaseSettings):
    """
    Manages application settings using Pydantic, reading from environment variables
    and optionally a .env file for local development.
    """

    # Configuration to load .env file (useful locally, ignored in Docker if not present)
    # Assumes .env is in the project root ('sapheneia/') relative to where script runs
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), '..', '..', '.env'),
        env_file_encoding='utf-8',
        extra='ignore'  # Ignore extra variables not defined in the model
    )

    # --- Core API Settings ---
    API_SECRET_KEY: str = "default_secret_key_please_change"  # MUST be set in .env or environment
    LOG_LEVEL: str = "INFO"
    API_PORT: int = 8000  # Default port for Uvicorn
    API_HOST: str = "0.0.0.0"  # Listen on all interfaces, crucial for Docker
    ENVIRONMENT: str = "development"  # Can be: development, staging, production

    # --- CORS Settings ---
    CORS_ALLOWED_ORIGINS: str = "http://localhost:8080,http://localhost:3000"  # Comma-separated list
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "*"

    # --- Rate Limiting Settings ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60  # Default: 60 requests per minute
    RATE_LIMIT_INFERENCE_PER_MINUTE: int = 10  # Stricter limit for inference endpoints
    RATE_LIMIT_STORAGE_URI: str = "memory://"  # Can be "redis://localhost:6379" for distributed

    # --- Request Size Limits (Phase 5) ---
    MAX_REQUEST_SIZE: int = 10 * 1024 * 1024  # 10MB - Maximum request body size
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024   # 50MB - Maximum file upload size

    # --- MLOps / Aleutian Placeholders ---
    # These will be automatically populated by docker-compose in Aleutian
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"  # Local MLflow default
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"  # Local Redis default
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"  # Local Redis default

    # --- Model Specific Settings Defaults (can be overridden by environment vars) ---
    # TimesFM-2.0 Defaults
    TIMESFM20_DEFAULT_BACKEND: str = "cpu"
    TIMESFM20_DEFAULT_CONTEXT_LEN: int = 64  # Changed from 100 to 64 as requested
    TIMESFM20_DEFAULT_HORIZON_LEN: int = 24
    TIMESFM20_DEFAULT_CHECKPOINT: Optional[str] = "google/timesfm-2.0-500m-pytorch"  # HF checkpoint
    TIMESFM20_DEFAULT_LOCAL_PATH: Optional[str] = None  # Relative path in forecast/models/timesfm20/local/
    TIMESFM20_DEFAULT_MLFLOW_NAME: Optional[str] = "timesfm20-production"  # Example MLflow model name
    TIMESFM20_DEFAULT_MLFLOW_STAGE: str = "Production"

    @field_validator('API_SECRET_KEY')
    @classmethod
    def validate_api_key(cls, v: str, info) -> str:
        """
        Validate that API_SECRET_KEY is changed from default in production.

        Raises:
            ValueError: If default key is used in production environment
        """
        environment = info.data.get('ENVIRONMENT', 'development')

        if v == "default_secret_key_please_change":
            if environment == "production":
                raise ValueError(
                    "❌ CRITICAL SECURITY ERROR: API_SECRET_KEY must be changed from default value in production! "
                    "Set API_SECRET_KEY in your .env file or environment variables."
                )
            else:
                # Log warning but allow in development/staging
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("⚠️  WARNING: Using default API_SECRET_KEY! This is NOT secure for production.")

        # Validate minimum length
        if len(v) < 32:
            if environment == "production":
                raise ValueError(
                    "❌ SECURITY ERROR: API_SECRET_KEY must be at least 32 characters long in production."
                )
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"⚠️  WARNING: API_SECRET_KEY is only {len(v)} characters. Recommended: 32+ characters.")

        return v

    def get_cors_origins(self) -> list[str]:
        """Convert comma-separated CORS origins string to list."""
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(',') if origin.strip()]

    def get_cors_methods(self) -> list[str]:
        """Convert comma-separated CORS methods string to list."""
        return [method.strip() for method in self.CORS_ALLOW_METHODS.split(',') if method.strip()]


# Instantiate settings early to make them available for import
settings = Settings()

# --- Configure Root Logger ---
# Basic configuration, customize further if needed (e.g., file logging)
log_level_numeric = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level_numeric,
    format='%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s',  # Wider name field
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Optional: Adjust log levels for noisy libraries
logging.getLogger("uvicorn.access").setLevel(max(log_level_numeric, logging.WARNING))
logging.getLogger("urllib3").setLevel(max(log_level_numeric, logging.INFO))
logging.getLogger("huggingface_hub").setLevel(max(log_level_numeric, logging.INFO))
logging.getLogger("mlflow.tracking").setLevel(max(log_level_numeric, logging.WARNING))  # MLflow can be verbose

logger = logging.getLogger(__name__)  # Logger for this config module
logger.info("=" * 80)
logger.info("Sapheneia API Configuration")
logger.info("=" * 80)
logger.info(f"Log Level: {settings.LOG_LEVEL}")
logger.info(f"API Host:Port: {settings.API_HOST}:{settings.API_PORT}")
logger.info(f"MLflow Tracking URI: {settings.MLFLOW_TRACKING_URI}")
logger.info(f"TimesFM-2.0 Default Context Length: {settings.TIMESFM20_DEFAULT_CONTEXT_LEN}")
logger.info(f"TimesFM-2.0 Default Horizon Length: {settings.TIMESFM20_DEFAULT_HORIZON_LEN}")
logger.info("=" * 80)
