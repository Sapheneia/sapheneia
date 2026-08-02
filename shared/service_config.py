"""Shared production-hardening validator for service API keys.

``trading/core/config.py`` already had the right idea: refuse to boot when
``ENVIRONMENT=production`` and the API key is still a default or too short.
That guard existed at exactly one of five sites. Per CLAUDE.md §5.4, a fix that
belongs at multiple sites belongs at *all* of them, so it lives here now and
every service config calls it.

Development and staging keep the permissive behaviour (warn, don't fail) so an
empty key still means "auth off" on a local box.
"""

from __future__ import annotations

import logging

MIN_PRODUCTION_KEY_LENGTH = 32

#: Placeholder values that must never survive into production.
DEFAULT_PLACEHOLDERS = frozenset(
    {
        "",
        "change_me",
        "changeme",
        "default_trading_api_key_please_change",
        "change_me_in_production_abc123",
        "change_me_trading_key_must_be_32_chars_or_more",
    }
)


def validate_api_key(
    value: str,
    *,
    environment: str,
    field_name: str,
    required: bool = True,
) -> str:
    """Validate an API key against the deployment environment.

    In production: a placeholder, empty (when ``required``), or short key is a
    hard boot failure. Elsewhere: a warning.

    Raises:
        ValueError: on an unusable key in production.
    """
    logger = logging.getLogger("sapheneia.config")
    is_production = environment.strip().lower() == "production"
    normalised = value.strip()

    def fail_or_warn(problem: str) -> None:
        message = f"{field_name}: {problem}"
        if is_production:
            raise ValueError(
                f"SECURITY: {message} Set {field_name} in your .env or environment before "
                f"running with ENVIRONMENT=production."
            )
        logger.warning("%s (allowed outside production)", message)

    if normalised.lower() in DEFAULT_PLACEHOLDERS:
        if normalised == "" and not required:
            return value
        fail_or_warn("is empty or still set to a placeholder value.")
        return value

    if "#" in normalised:
        # Catches the .env inline-comment trap, where `KEY=  # comment` parses
        # the comment itself as the value.
        fail_or_warn(
            "contains a '#', which usually means an inline .env comment was "
            "parsed as the value. Put comments on their own line."
        )
        return value

    if len(normalised) < MIN_PRODUCTION_KEY_LENGTH:
        fail_or_warn(
            f"is only {len(normalised)} characters; "
            f"{MIN_PRODUCTION_KEY_LENGTH}+ is required in production."
        )

    return value
