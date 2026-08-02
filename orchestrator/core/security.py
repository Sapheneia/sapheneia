"""Bearer auth for orchestrator endpoints."""

from __future__ import annotations

from shared.service_security import create_api_key_header, make_bearer_dependency

from .config import settings

get_api_key = make_bearer_dependency(
    lambda: settings.API_KEY,
    service_name="orchestrator",
)

__all__ = ["get_api_key", "create_api_key_header"]
