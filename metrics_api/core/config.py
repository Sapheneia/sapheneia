"""
Metrics API Configuration

Environment-based configuration for the Metrics API service.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Metrics API Settings"""

    # API Settings
    HOST: str = Field(default="0.0.0.0", description="API host")
    PORT: int = Field(default=8001, description="API port")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Security (optional - for future API key authentication)
    SECRET_KEY: str = Field(default="", description="API authentication key (optional)")

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_prefix = "METRICS_API_"
        extra = "ignore"  # Ignore extra fields from .env


settings = Settings()
