"""Bearer auth dependency for the data service.

If ``DATA_API_KEY`` is empty, auth is disabled and any caller is allowed — the
intra-cluster development default, matching the metrics service. Production
deployments are stopped from booting that way by the validator in
``data/core/config.py``.
"""

from __future__ import annotations

from shared.service_security import create_api_key_header, make_bearer_dependency

from .config import settings

get_api_key = make_bearer_dependency(
    lambda: settings.API_KEY,
    service_name="data",
    # Explicit: an empty key disables auth here, preserving this service's
    # documented intra-cluster default. Production is guarded by the config
    # validator, which refuses to boot on an empty key.
    open_when_unset=True,
)

__all__ = ["get_api_key", "create_api_key_header"]
