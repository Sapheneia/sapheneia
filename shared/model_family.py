"""Canonical model-family slugs shared across services (§3.5)."""

from __future__ import annotations

from enum import StrEnum


class ModelFamily(StrEnum):
    """Canonical family identifiers used across the orchestrator and clients.

    The enum *value* is the stable family slug persisted in the ``models.family``
    column / returned by the forecast service registry. The forecast service also
    exposes model-specific route prefixes (e.g. ``/forecast/v1/timesfm20/inference``)
    that differ from the family slug; ``route_suffix`` maps a family to that prefix.
    """

    CHRONOS = "chronos"
    TIMESFM = "timesfm"

    @property
    def route_suffix(self) -> str:
        """Return the forecast-service route segment for this family.

        ``timesfm`` routes under ``/forecast/v1/timesfm20/inference`` (legacy model
        name kept as the URL prefix), all other families match their slug.
        """
        return "timesfm20" if self is ModelFamily.TIMESFM else self.value

    @staticmethod
    def from_model_id(model_id: str) -> ModelFamily:
        """Infer the family from a model identifier (e.g. ``amazon/chronos-t5-tiny``)."""
        lowered = model_id.lower()
        if "chronos" in lowered:
            return ModelFamily.CHRONOS
        if "timesfm" in lowered:
            return ModelFamily.TIMESFM
        raise ValueError(f"Unknown model family for model_id={model_id!r}")
