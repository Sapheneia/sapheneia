"""Runtime config for sapheneia-mcp.

Reads downstream service URLs and per-service Bearer tokens from env. The
*one* token the agent presents to this MCP is ``SAPHENEIA_MCP_TOKEN``.
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.service_config import validate_api_key


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SAPHENEIA_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    #: The single agent ↔ MCP token. Enforced on the SSE transport; see
    #: ``ALLOW_UNAUTHENTICATED_SSE`` for the escape hatch.
    TOKEN: str = ""
    #: SSE refuses to start without a TOKEN. This process holds every
    #: downstream service key, so an unauthenticated listener would launder
    #: anonymous requests into authenticated ones against every leaf service.
    #: Set True only for an isolated single-user box where that is acceptable.
    ALLOW_UNAUTHENTICATED_SSE: bool = False

    ORCHESTRATOR_URL: str = "http://orchestrator:8000"
    DATA_URL: str = "http://data:8000"
    #: Empty means "route each model to its own container via
    #: shared.model_registry". Set only for a single-model deployment.
    FORECAST_URL: str = ""
    TRADING_URL: str = "http://trading:9000"
    METRICS_URL: str = "http://metrics:8000"

    ORCHESTRATOR_API_KEY: str = ""
    DATA_API_KEY: str = ""
    FORECAST_API_KEY: str = ""
    TRADING_API_KEY: str = ""
    METRICS_API_KEY: str = ""

    HTTP_TIMEOUT: float = 60.0

    @field_validator("TOKEN")
    @classmethod
    def _check_token(cls, v: str, info) -> str:
        """The token guarding the process that holds every downstream key.

        It was the one credential exempt from the strength/placeholder checks
        every service key goes through.
        """
        return validate_api_key(
            v,
            environment=info.data.get("ENVIRONMENT", "development"),
            field_name="SAPHENEIA_MCP_TOKEN",
            required=False,
        )

    @field_validator("ALLOW_UNAUTHENTICATED_SSE")
    @classmethod
    def _no_open_sse_in_production(cls, v: bool, info) -> bool:
        if v and info.data.get("ENVIRONMENT", "development").strip().lower() == "production":
            raise ValueError(
                "SECURITY: SAPHENEIA_MCP_ALLOW_UNAUTHENTICATED_SSE cannot be true when "
                "ENVIRONMENT=production. This process holds every downstream service key."
            )
        return v


settings = McpSettings()
