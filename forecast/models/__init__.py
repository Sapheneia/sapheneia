"""
Sapheneia model accessors.

This module used to carry a second, independent ``MODEL_REGISTRY`` dict: nine
models on ports 8001/8100-8107 that no longer corresponded to anything in
``docker-compose.yml``. ``GET /models`` served *that* one, while both READMEs
documented ``forecast/models/registry.py`` — six models on ports 12710-12721 —
as the source of truth, and nothing imported it.

There is now one registry (``shared.model_registry``); these helpers read it.
"""

from typing import Any

from shared.model_registry import all_models, as_dicts, by_id


def get_available_models() -> list[str]:
    """Model IDs that are wired and expected to work."""
    return [m.model_id for m in all_models() if m.is_working]


def get_model_info(model_id: str) -> dict[str, Any]:
    """Information about a specific model.

    Raises:
        KeyError: If model_id is not in the registry.
    """
    info = by_id(model_id)
    if info is None:
        raise KeyError(f"Model '{model_id}' not found in registry")
    return {
        "model_id": info.model_id,
        "family": info.family.value,
        "container": info.container,
        "port": info.port,
        "status": info.status,
        "notes": info.notes,
        "base_url": info.base_url,
    }


def get_all_models_info() -> dict[str, dict[str, Any]]:
    """The complete registry, keyed by model ID."""
    return {d["model_id"]: d for d in as_dicts()}
