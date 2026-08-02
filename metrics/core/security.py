"""Bearer auth dependency for the metrics service.

If ``METRICS_API_KEY`` is unset, auth is open — preserving the v1 behaviour for
intra-cluster development setups. Production deployments are stopped from
booting that way by the validator in ``metrics/core/config.py``.
"""

from __future__ import annotations

from shared.service_security import create_api_key_header, make_bearer_dependency

from .config import settings

get_api_key = make_bearer_dependency(
    lambda: settings.API_KEY,
    service_name="metrics",
    # Explicit: an empty key disables auth here, preserving this service's
    # documented intra-cluster default. Production is guarded by the config
    # validator, which refuses to boot on an empty key.
    open_when_unset=True,
)

__all__ = ["get_api_key", "create_api_key_header"]
