"""Bearer auth dependency for the metrics service.

If ``METRICS_API_KEY`` is unset, auth is open — preserving the v1 behaviour for
intra-cluster development setups. Production deployments are stopped from
booting that way by the validator in ``metrics/core/config.py``.
"""

from __future__ import annotations

from shared.service_security import create_api_key_header, make_bearer_dependency

from .config import Settings

_settings = Settings()

get_api_key = make_bearer_dependency(
    lambda: _settings.API_KEY,
    service_name="metrics",
)

__all__ = ["get_api_key", "create_api_key_header"]
