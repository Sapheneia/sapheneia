"""Shared Bearer-auth dependency for every Sapheneia FastAPI service.

Replaces five near-identical ``get_api_key`` implementations that had drifted
apart in two ways that mattered:

* they compared keys with ``!=`` (timing-variable) rather than
  ``secrets.compare_digest``;
* two of them logged fragments of the credential (one logged a prefix of the
  *expected* key plus its exact length, on a path any unauthenticated caller
  could trigger at will).

Neither is reachable-critical on a single-tenant box, but there is no reason to
keep five copies of a security primitive when one will do.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def _client_host(request: Request | None) -> str:
    if request is None or request.client is None:
        return "unknown"
    return request.client.host


def make_bearer_dependency(
    expected_key: Callable[[], str],
    *,
    service_name: str,
    open_when_unset: bool = True,
) -> Callable:
    """Build a FastAPI dependency that validates a Bearer token.

    Args:
        expected_key: Called per-request so config reloads are picked up.
        service_name: Used only for the logger name.
        open_when_unset: When True an empty configured key disables auth
            (the intra-cluster development default). Production hardening is
            enforced separately by ``shared.service_config``, which refuses to
            boot with an empty key when ``ENVIRONMENT=production``.
    """
    logger = logging.getLogger(f"sapheneia.{service_name}.auth")

    async def get_api_key(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> str:
        expected = expected_key()
        if not expected:
            if open_when_unset:
                return ""
            logger.error("Auth is required but no API key is configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server auth misconfigured",
            )
        if credentials is None or credentials.scheme.lower() != "bearer":
            logger.warning("Auth failed (missing bearer token) from %s", _client_host(request))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Bearer token",
                headers=_UNAUTHORIZED_HEADERS,
            )
        # Never log the provided or expected key, nor their lengths.
        if not secrets.compare_digest(credentials.credentials, expected):
            logger.warning("Auth failed (invalid key) from %s", _client_host(request))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers=_UNAUTHORIZED_HEADERS,
            )
        return credentials.credentials

    return get_api_key


def create_api_key_header(api_key: str) -> dict[str, str]:
    """Build an Authorization header for outbound calls."""
    return {"Authorization": f"Bearer {api_key}"}
