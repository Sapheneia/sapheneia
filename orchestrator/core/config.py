"""Pydantic settings for the orchestrator service."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORCHESTRATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    API_KEY: str = ""

    # Downstream service URLs
    DATA_SERVICE_URL: str = "http://data:8000"
    FORECAST_SERVICE_URL: str = "http://forecast:8000"
    TRADING_SERVICE_URL: str = "http://trading:9000"
    METRICS_SERVICE_URL: str = "http://metrics:8000"

    # Downstream auth (per-service tokens; orchestrator holds all)
    FORECAST_API_KEY: str = ""
    TRADING_API_KEY: str = ""
    METRICS_API_KEY: str = ""
    DATA_API_KEY: str = ""

    # Concurrency caps
    MAX_CONCURRENT_RUNS: int = 4
    MAX_PER_MODEL: int = 2

    # Inner-loop timeouts (seconds)
    DATA_TIMEOUT: float = 60.0
    FORECAST_TIMEOUT: float = 300.0
    TRADING_TIMEOUT: float = 30.0
    METRICS_TIMEOUT: float = 30.0

    # Heartbeat reconciler
    HEARTBEAT_INTERVAL: float = 30.0
    HEARTBEAT_STALE_AFTER: float = 300.0  # 5 minutes


settings = OrchestratorSettings()
