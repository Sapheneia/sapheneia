"""Guard against the .env inline-comment trap.

`KEY=` followed by an inline `# comment` makes python-dotenv parse the comment
text as the value. For the credential block that inverts the intent: instead of
"empty disables auth", auth is ENABLED with a password published in this
repository. It is invisible on inspection, so it gets a test.
"""

from __future__ import annotations

import pathlib

import pytest
from dotenv import dotenv_values

TEMPLATE = pathlib.Path(__file__).resolve().parents[1] / ".env.template"
SECRET_SUFFIXES = ("_KEY", "_TOKEN", "_PASSWORD", "_SECRET")


@pytest.fixture(scope="module")
def parsed() -> dict[str, str | None]:
    return dotenv_values(TEMPLATE)


def test_template_exists_and_parses(parsed) -> None:
    assert parsed, ".env.template did not parse into any variables"


def test_no_value_contains_a_comment_marker(parsed) -> None:
    offenders = {k: v for k, v in parsed.items() if v and "#" in v}
    assert not offenders, (
        f"These values swallowed an inline comment: {offenders}. Move the comment to its own line."
    )


def test_secret_values_are_empty_or_explicit_placeholders(parsed) -> None:
    for key, value in parsed.items():
        if not key.endswith(SECRET_SUFFIXES):
            continue
        if not value:
            continue
        assert "#" not in value, f"{key} parsed a comment as its value: {value!r}"
        assert not value.startswith(" "), f"{key} has a leading space: {value!r}"


def test_mcp_token_defaults_to_empty(parsed) -> None:
    """Empty must mean empty — the SSE transport refuses to start on it."""
    assert parsed.get("SAPHENEIA_MCP_TOKEN") in ("", None)


def test_orchestrator_stale_threshold_exceeds_the_forecast_timeout(parsed) -> None:
    """Otherwise the reconciler fails runs that are merely waiting on a model."""
    stale = float(parsed.get("ORCHESTRATOR_HEARTBEAT_STALE_AFTER") or 0)
    # Default forecast timeout in orchestrator/core/config.py.
    assert stale > 300.0, f"stale threshold {stale}s is not above the 300s forecast timeout"
