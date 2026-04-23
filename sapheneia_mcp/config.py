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
    TOKEN: str = ""  # the single agent ↔ MCP token

    ORCHESTRATOR_URL: str = "http://orchestrator:8000"
    DATA_URL: str = "http://data:8000"
    FORECAST_URL: str = "http://forecast:8000"
    TRADING_URL: str = "http://trading:9000"
    METRICS_URL: str = "http://metrics:8000"

    ORCHESTRATOR_API_KEY: str = ""
    DATA_API_KEY: str = ""
    FORECAST_API_KEY: str = ""
    TRADING_API_KEY: str = ""
    METRICS_API_KEY: str = ""

    HTTP_TIMEOUT: float = 60.0


settings = McpSettings()
