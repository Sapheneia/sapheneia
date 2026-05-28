"""
Metrics API Configuration

Environment-based configuration for the Metrics API service.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Metrics API Settings"""

    # API Settings
    HOST: str = Field(default="0.0.0.0", description="API host")
    PORT: int = Field(default=8001, description="API port")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Security: Bearer token; empty disables auth (intra-cluster default)
    API_KEY: str = Field(default="", description="Bearer token; empty disables auth")

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_prefix = "METRICS_"
        extra = "ignore"  # Ignore extra fields from .env


settings = Settings()
