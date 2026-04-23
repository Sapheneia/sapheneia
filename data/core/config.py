"""Pydantic settings for the data service."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    API_KEY: str = ""  # empty disables auth (matches metrics' v1 baseline)
    YFINANCE_TIMEOUT: float = 30.0
    YFINANCE_MAX_CONCURRENCY: int = 8


settings = DataSettings()
