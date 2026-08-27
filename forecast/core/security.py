"""
API Security and Authentication for the forecast service.

Delegates to ``shared.service_security`` so all services validate credentials
the same way (constant-time comparison, and no credential material in logs).
"""

from shared.service_security import create_api_key_header, make_bearer_dependency

from .config import settings

# Fail closed: an empty API_SECRET_KEY rejects every request rather than
# disabling auth. This service publishes seven containers on host ports, and it
# was fail-closed before the shared dependency existed.
get_api_key = make_bearer_dependency(
    lambda: settings.API_SECRET_KEY,
    service_name="forecast",
    open_when_unset=False,
)

__all__ = ["get_api_key", "create_api_key_header"]
