"""
API Security and Authentication for the forecast service.

Delegates to ``shared.service_security`` so all services validate credentials
the same way (constant-time comparison, and no credential material in logs).
"""

from shared.service_security import create_api_key_header, make_bearer_dependency

from .config import settings

get_api_key = make_bearer_dependency(
    lambda: settings.API_SECRET_KEY,
    service_name="forecast",
)

__all__ = ["get_api_key", "create_api_key_header"]
