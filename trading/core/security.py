"""
API Security and Authentication for the Trading Strategies API.

Delegates to ``shared.service_security`` so all services validate credentials
the same way (constant-time comparison, and no credential material in logs).

Trading keeps ``open_when_unset=False``: unlike the intra-cluster services, it
has no "auth disabled" mode — an unset key is a misconfiguration, not a
development convenience.
"""

from shared.service_security import (
    bearer_scheme as security_scheme,
)
from shared.service_security import (
    create_api_key_header,
    make_bearer_dependency,
)

from .config import settings

get_api_key = make_bearer_dependency(
    lambda: settings.TRADING_API_KEY,
    service_name="trading",
    open_when_unset=False,
)

__all__ = ["get_api_key", "create_api_key_header", "security_scheme"]
