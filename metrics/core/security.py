"""Bearer auth dependency for the metrics service."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings

_settings = Settings()
bearer_scheme = HTTPBearer(auto_error=False)


def get_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Validate the metrics ``METRICS_API_KEY``.

    If unset (empty string), auth is open — preserving the v1 behaviour for
    intra-cluster development setups. In production, set ``METRICS_API_KEY``.
    """
    expected = _settings.API_KEY
    if not expected:
        return ""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
