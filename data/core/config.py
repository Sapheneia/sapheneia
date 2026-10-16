"""Pydantic settings for the data service."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.service_config import validate_api_key


class DataSettings(BaseSettings):
    """Settings loaded from the environment with prefix ``DATA_``.

    The TimescaleDB connection variables (``TIMESCALEDB_*``) are read directly
    by ``shared.db.dsn_from_env`` and intentionally not duplicated here.
    """

    model_config = SettingsConfigDict(
        env_prefix="DATA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    API_KEY: str = ""  # empty disables auth (matches metrics' v1 baseline)
    YFINANCE_TIMEOUT: float = 30.0
    YFINANCE_MAX_CONCURRENCY: int = 8
    #: Requests/minute/client. Also caps how fast a caller can drive upstream
    #: yfinance fetches through the read-through cache.
    RATE_LIMIT_PER_MINUTE: int = 240

    @field_validator("API_KEY")
    @classmethod
    def _check_api_key(cls, v: str, info) -> str:
        return validate_api_key(
            v,
            environment=info.data.get("ENVIRONMENT", "development"),
            field_name="DATA_API_KEY",
        )


settings = DataSettings()
