"""
Metrics API Configuration

Environment-based configuration for the Metrics API service.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from shared.service_config import validate_api_key


class Settings(BaseSettings):
    """Metrics API Settings"""

    # Deployment environment. Declared before API_KEY so the validator below
    # can read it from `info.data` (pydantic validates in declaration order).
    ENVIRONMENT: str = Field(
        default="development", description="development | staging | production"
    )

    # API Settings
    HOST: str = Field(default="0.0.0.0", description="API host")
    PORT: int = Field(default=8001, description="API port")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Security: Bearer token; empty disables auth (intra-cluster default)
    API_KEY: str = Field(default="", description="Bearer token; empty disables auth")

    RATE_LIMIT_PER_MINUTE: int = Field(default=240, description="Requests/minute/client")

    @field_validator("API_KEY")
    @classmethod
    def _check_api_key(cls, v: str, info) -> str:
        return validate_api_key(
            v,
            environment=info.data.get("ENVIRONMENT", "development"),
            field_name="METRICS_API_KEY",
        )

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_prefix = "METRICS_"
        extra = "ignore"  # Ignore extra fields from .env


settings = Settings()
