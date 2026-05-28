"""Canonical model registry — single source of truth for working models.

Per the v2 refactor, only models with a Sapheneia container implementation are
listed here. The registry replaces the prior bash-array registry that lived in
``scripts/model-manager.sh`` (deleted with Aleutian).

To add a new model:
  1. Add a row to ``WORKING_MODELS`` below with its HuggingFace ID,
     family, container name, and assigned port.
  2. Add a service block to ``docker-compose.yml`` (copy an existing
     entry, change MODEL_VARIANT and the port).
  3. If it's a new model family, add a service module under
     ``forecast/models/{family}/`` mirroring ``chronos`` or ``timesfm20``.
  4. Append the new model to ``simulations/templates/combinations.example.yaml``
     so the agent path picks it up.

Status values:
  ``working``  — fully wired, container builds, inference returns valid data
  ``broken``   — known to fail; do not deploy
  ``planned``  — placeholder for future implementation
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelInfo:
    model_id: str  # HuggingFace ID, e.g. "amazon/chronos-t5-tiny"
    family: str  # "chronos" | "timesfm"
    container: str  # docker-compose service name
    port: int  # host port (mapped to 8000 inside the container)
    status: str = "working"
    notes: str = ""


WORKING_MODELS: list[ModelInfo] = [
    ModelInfo("amazon/chronos-t5-tiny", "chronos", "forecast-chronos-t5-tiny", 12710),
    ModelInfo("amazon/chronos-t5-mini", "chronos", "forecast-chronos-t5-mini", 12711),
    ModelInfo("amazon/chronos-t5-small", "chronos", "forecast-chronos-t5-small", 12712),
    ModelInfo("amazon/chronos-t5-base", "chronos", "forecast-chronos-t5-base", 12713),
    ModelInfo("amazon/chronos-t5-large", "chronos", "forecast-chronos-t5-large", 12714),
    ModelInfo("google/timesfm-2.0-500m-pytorch", "timesfm", "forecast-timesfm-2-0", 12721),
]


def all_models() -> list[ModelInfo]:
    return list(WORKING_MODELS)


def by_id(model_id: str) -> ModelInfo | None:
    for m in WORKING_MODELS:
        if m.model_id == model_id:
            return m
    return None


def by_family(family: str) -> list[ModelInfo]:
    return [m for m in WORKING_MODELS if m.family == family]


def as_dicts() -> list[dict]:
    return [asdict(m) for m in WORKING_MODELS]
