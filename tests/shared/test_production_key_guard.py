"""Every service must refuse to boot in production with an unusable API key.

The guard originally existed only in the trading service — and was inert even
there, because ``ENVIRONMENT`` was declared *after* ``TRADING_API_KEY``.
Pydantic validates fields in declaration order and exposes only
already-validated fields through ``info.data``, so the key validator always read
the ``"development"`` fallback no matter what ``ENVIRONMENT`` was set to.

That is a silent failure mode: the guard looks present in code review, has a
test, and does nothing. This asserts *behaviour* at every site (CLAUDE.md §5.4)
rather than the declaration order, so it stays true however the configs are
refactored.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pydantic
import pytest

# (import path, class name, env var holding the key)
CONFIGS = [
    ("trading.core.config", "TradingSettings", "TRADING_API_KEY"),
    ("orchestrator.core.config", "OrchestratorSettings", "ORCHESTRATOR_API_KEY"),
    ("data.core.config", "DataSettings", "DATA_API_KEY"),
    ("metrics.core.config", "Settings", "METRICS_API_KEY"),
]

# Each config reads ENVIRONMENT under its own prefix (or bare, for trading).
ENV_ALIASES = [
    "ENVIRONMENT",
    "TRADING_ENVIRONMENT",
    "ORCHESTRATOR_ENVIRONMENT",
    "DATA_ENVIRONMENT",
    "METRICS_ENVIRONMENT",
]


def _load(module_path: str, class_name: str):
    import importlib

    return getattr(importlib.import_module(module_path), class_name)


@pytest.mark.parametrize(("module_path", "class_name", "key_var"), CONFIGS)
def test_short_key_refuses_to_boot_in_production(module_path, class_name, key_var) -> None:
    settings_cls = _load(module_path, class_name)
    env = {alias: "production" for alias in ENV_ALIASES}
    env[key_var] = "tooshort"
    with patch.dict(os.environ, env), pytest.raises(pydantic.ValidationError, match="SECURITY"):
        settings_cls(_env_file=None)


@pytest.mark.parametrize(("module_path", "class_name", "key_var"), CONFIGS)
def test_strong_key_boots_in_production(module_path, class_name, key_var) -> None:
    settings_cls = _load(module_path, class_name)
    env = {alias: "production" for alias in ENV_ALIASES}
    env[key_var] = "k" * 48
    with patch.dict(os.environ, env):
        settings = settings_cls(_env_file=None)
    assert settings.ENVIRONMENT == "production"


@pytest.mark.parametrize(("module_path", "class_name", "key_var"), CONFIGS)
def test_short_key_is_allowed_outside_production(module_path, class_name, key_var) -> None:
    settings_cls = _load(module_path, class_name)
    env = {alias: "development" for alias in ENV_ALIASES}
    env[key_var] = "tooshort"
    with patch.dict(os.environ, env):
        settings_cls(_env_file=None)  # must not raise


@pytest.mark.parametrize(("module_path", "class_name", "key_var"), CONFIGS)
def test_inline_comment_value_refuses_to_boot_in_production(
    module_path, class_name, key_var
) -> None:
    """The .env inline-comment trap must not slip through as a "valid" key."""
    settings_cls = _load(module_path, class_name)
    env = {alias: "production" for alias in ENV_ALIASES}
    env[key_var] = "# empty disables auth"
    with patch.dict(os.environ, env), pytest.raises(pydantic.ValidationError, match="SECURITY"):
        settings_cls(_env_file=None)
