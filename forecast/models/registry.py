"""Model registry for the forecast service.

The canonical definition lives in :mod:`shared.model_registry` because the
orchestrator needs it too — it resolves ``model_id -> container base URL`` from
the same table in order to reach the container that actually holds a model.
Keeping two copies is what let the service's ``GET /models`` drift onto a stale
list of models and ports that no longer existed.

This module re-exports the shared registry so the documented import path
(``forecast/models/registry.py``) keeps working.

To add a new model, edit ``shared/model_registry.py`` and follow the checklist
in its docstring.
"""

from __future__ import annotations

from shared.model_registry import (
    INTERNAL_PORT,
    WORKING_MODELS,
    ModelInfo,
    UnknownModelError,
    all_models,
    as_dicts,
    by_family,
    by_id,
    require,
)

__all__ = [
    "INTERNAL_PORT",
    "WORKING_MODELS",
    "ModelInfo",
    "UnknownModelError",
    "all_models",
    "as_dicts",
    "by_family",
    "by_id",
    "require",
]
