"""Runtime config for sapheneia-mcp.

Reads downstream service URLs and per-service Bearer tokens from env. The
*one* token the agent presents to this MCP is ``SAPHENEIA_MCP_TOKEN``.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SAPHENEIA_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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


settings = McpSettings()
