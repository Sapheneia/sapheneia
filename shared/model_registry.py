"""Canonical model registry — the single source of truth for working models.

This lives in ``shared/`` rather than ``forecast/`` because both sides need it:

* the **forecast service** serves it from ``GET /models``;
* the **orchestrator** resolves ``model_id -> base_url`` from it so that a run
  reaches the container that actually holds the requested model.

That second consumer is the reason this module exists. Each forecast container
loads exactly one model (pinned by ``MODEL_VARIANT``) into a process-global
pipeline, so "which model ran" is a property of *which container was called*,
not of a field in the request body. Routing therefore has to be resolved
before the request is sent.

To add a new model (this list is canonical; the READMEs link here):
  1. Add a row to ``WORKING_MODELS`` below with its HuggingFace ID, family,
     container name, and assigned host port.
  2. Add a service block to ``docker-compose.yml`` (copy an existing entry).
     It MUST set ``MODEL_VARIANT`` to the same HuggingFace ID and publish the
     same port — every family reads ``MODEL_VARIANT`` as its container pin, and
     ``tests/test_deployment_consistency.py`` fails the build if the two tables
     disagree.
  3. If it is a new model family, add a service module under
     ``forecast/models/{family}/`` mirroring ``chronos`` or ``timesfm20``, and
     give it a canonical ``POST /forecast`` endpoint returning a
     ``shared.contracts.ForecastEnvelope``.
  4. Append the new model to ``simulations/templates/combinations.example.yaml``
     so the agent path picks it up.

Status values:
  ``working``  — fully wired, container builds, inference returns valid data
  ``broken``   — known to fail; the orchestrator refuses to dispatch to it
  ``planned``  — placeholder for future implementation
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from .errors import ErrorCode, ValidationError
from .model_family import ModelFamily

#: Every forecast container listens on this port inside the compose network.
#: The per-model ``port`` field below is the *host* port published for direct
#: access; in-cluster routing always uses the container name and this port.
INTERNAL_PORT = 8000


@dataclass(frozen=True)
class ModelInfo:
    model_id: str  # HuggingFace ID, e.g. "amazon/chronos-t5-tiny"
    family: ModelFamily  # canonical family slug
    container: str  # docker-compose service name == in-network DNS name
    port: int  # host port (mapped to INTERNAL_PORT in the container)
    status: str = "working"
    notes: str = ""

    @property
    def base_url(self) -> str:
        """In-network base URL for this model's container.

        Overridable per deployment via ``FORECAST_BASE_URL_TEMPLATE`` so the
        topology is not a hardcoded literal (§3.5); the default matches the
        compose service names.
        """
        template = os.getenv("FORECAST_BASE_URL_TEMPLATE", "http://{container}:{port}")
        return template.format(container=self.container, port=INTERNAL_PORT)

    @property
    def forecast_path(self) -> str:
        """Canonical cross-family forecast route for this model."""
        return f"/forecast/v1/{self.family.route_suffix}/forecast"

    @property
    def legacy_inference_path(self) -> str:
        """Family-specific pre-contract route. Kept for direct/manual calls."""
        return f"/forecast/v1/{self.family.route_suffix}/inference"

    @property
    def is_working(self) -> bool:
        return self.status == "working"


WORKING_MODELS: list[ModelInfo] = [
    ModelInfo("amazon/chronos-t5-tiny", ModelFamily.CHRONOS, "forecast-chronos-t5-tiny", 12710),
    ModelInfo("amazon/chronos-t5-mini", ModelFamily.CHRONOS, "forecast-chronos-t5-mini", 12711),
    ModelInfo("amazon/chronos-t5-small", ModelFamily.CHRONOS, "forecast-chronos-t5-small", 12712),
    ModelInfo("amazon/chronos-t5-base", ModelFamily.CHRONOS, "forecast-chronos-t5-base", 12713),
    ModelInfo("amazon/chronos-t5-large", ModelFamily.CHRONOS, "forecast-chronos-t5-large", 12714),
    ModelInfo(
        "google/timesfm-2.0-500m-pytorch",
        ModelFamily.TIMESFM,
        "forecast-timesfm-2-0",
        12721,
    ),
]


class UnknownModelError(ValidationError):
    """Raised when a model_id is not present in the registry, or is not usable.

    Extends the shared ``ValidationError`` so the API boundary answers 400 with
    the registry's message (which lists every known model) instead of letting
    the generic handler turn it into an opaque 500.
    """

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details=details)
        # ValidationError hardcodes VALIDATION_ERROR; this is the more specific
        # code the shared enum already declares for exactly this case.
        self.error_code = ErrorCode.INVALID_MODEL


def all_models() -> list[ModelInfo]:
    return list(WORKING_MODELS)


def by_id(model_id: str) -> ModelInfo | None:
    for m in WORKING_MODELS:
        if m.model_id == model_id:
            return m
    return None


def require(model_id: str) -> ModelInfo:
    """Look up a model, raising if it is unknown or known-broken.

    The orchestrator uses this so an unroutable ``model_id`` fails loudly at
    dispatch time rather than silently landing on whichever model a shared
    container happened to load first.
    """
    info = by_id(model_id)
    if info is None:
        known = ", ".join(m.model_id for m in WORKING_MODELS)
        raise UnknownModelError(
            f"model_id={model_id!r} is not in the registry. Known models: {known}"
        )
    if not info.is_working:
        raise UnknownModelError(
            f"model_id={model_id!r} has status={info.status!r} and cannot be used"
        )
    return info


def by_family(family: ModelFamily | str) -> list[ModelInfo]:
    fam = ModelFamily(family) if not isinstance(family, ModelFamily) else family
    return [m for m in WORKING_MODELS if m.family is fam]


def as_dicts() -> list[dict]:
    out = []
    for m in WORKING_MODELS:
        d = asdict(m)
        d["family"] = m.family.value
        d["base_url"] = m.base_url
        out.append(d)
    return out
