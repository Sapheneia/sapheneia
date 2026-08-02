"""Pydantic settings for the orchestrator service."""

from __future__ import annotations

import socket

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.service_config import validate_api_key


def _default_owner_id() -> str:
    """Identity used to scope heartbeat reconciliation.

    Stable per *instance*, not per *process*. A uuid suffix would make every
    restart a new owner, so with RECONCILE_ALL_OWNERS disabled — the setting
    documented for multi-instance deployments — runs left `running` by a crash
    would be invisible to every future reconciler, which is precisely the
    failure the reconciler exists to prevent. In compose the hostname is the
    container name, which is exactly the identity we want.
    """
    return socket.gethostname()


class OrchestratorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORCHESTRATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    API_KEY: str = ""

    # Downstream service URLs
    DATA_SERVICE_URL: str = "http://data:8000"
    #: Empty means "route each model to its own container via
    #: shared.model_registry" — the correct setting for the compose stack.
    #: Set this only for a single-model deployment; it forces every model's
    #: request to one endpoint, which cannot serve a multi-model sweep.
    FORECAST_SERVICE_URL: str = ""
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

    # Requests/minute/client across all endpoints. Bearer validation on its own
    # has no lockout, and the write endpoints are the costliest in the system.
    # Sized for the agent polling every in-flight run on a short interval.
    RATE_LIMIT_PER_MINUTE: int = 1200

    # Heartbeat reconciler
    HEARTBEAT_INTERVAL: float = 30.0
    HEARTBEAT_STALE_AFTER: float = 900.0  # 15 minutes; > FORECAST_TIMEOUT with headroom

    #: Identity of this orchestrator process. Runs it creates are stamped with
    #: it, and the reconciler only fails runs it owns.
    OWNER_ID: str = Field(default_factory=_default_owner_id)
    #: Single-instance deployments should reconcile orphaned runs left behind by
    #: a previous process (same host, new OWNER_ID). Set False when running more
    #: than one orchestrator against the same database.
    RECONCILE_ALL_OWNERS: bool = True

    @field_validator("API_KEY")
    @classmethod
    def _check_api_key(cls, v: str, info) -> str:
        return validate_api_key(
            v,
            environment=info.data.get("ENVIRONMENT", "development"),
            field_name="ORCHESTRATOR_API_KEY",
        )


settings = OrchestratorSettings()
