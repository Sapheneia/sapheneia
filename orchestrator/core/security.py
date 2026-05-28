"""Bearer auth for orchestrator endpoints."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def get_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if not settings.API_KEY:
        return ""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Missing Bearer token", {"WWW-Authenticate": "Bearer"})
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(401, "Invalid API key", {"WWW-Authenticate": "Bearer"})
    return credentials.credentials
