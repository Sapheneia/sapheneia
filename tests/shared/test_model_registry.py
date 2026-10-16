"""Tests for the shared model family enum and registry.

These are the single source of truth for "which model runs where", so the
routing they drive is worth pinning down explicitly.
"""

from __future__ import annotations

import pytest

from shared.model_family import ModelFamily
from shared.model_registry import (
    INTERNAL_PORT,
    WORKING_MODELS,
    UnknownModelError,
    all_models,
    as_dicts,
    by_family,
    by_id,
    require,
)

TINY = "amazon/chronos-t5-tiny"
TIMESFM = "google/timesfm-2.0-500m-pytorch"


# --- ModelFamily ----------------------------------------------------------


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        (TINY, ModelFamily.CHRONOS),
        ("amazon/chronos-bolt-base", ModelFamily.CHRONOS),
        ("AMAZON/CHRONOS-T5-LARGE", ModelFamily.CHRONOS),
        (TIMESFM, ModelFamily.TIMESFM),
        ("google/TimesFM-1.0", ModelFamily.TIMESFM),
    ],
)
def test_from_model_id(model_id, expected) -> None:
    assert ModelFamily.from_model_id(model_id) is expected


def test_from_model_id_raises_on_unknown_family() -> None:
    """Unknown input must raise, not silently fall through to a default.

    The MCP passthrough used to do `"chronos" if "chronos" in id else "timesfm20"`,
    which routed a typo'd model to timesfm20 instead of erroring.
    """
    with pytest.raises(ValueError, match="Unknown model family"):
        ModelFamily.from_model_id("acme/mystery-model")


def test_route_suffix_maps_timesfm_to_its_legacy_url_segment() -> None:
    assert ModelFamily.TIMESFM.route_suffix == "timesfm20"
    assert ModelFamily.CHRONOS.route_suffix == "chronos"


# --- registry -------------------------------------------------------------


def test_registry_is_not_empty_and_ids_are_unique() -> None:
    ids = [m.model_id for m in all_models()]
    assert ids
    assert len(ids) == len(set(ids))


def test_ports_are_unique() -> None:
    ports = [m.port for m in WORKING_MODELS]
    assert len(ports) == len(set(ports)), "two models share a host port"


def test_containers_are_unique() -> None:
    names = [m.container for m in WORKING_MODELS]
    assert len(names) == len(set(names))


def test_base_url_targets_the_container_on_the_internal_port() -> None:
    info = require(TINY)
    assert info.base_url == f"http://forecast-chronos-t5-tiny:{INTERNAL_PORT}"


def test_forecast_path_is_the_canonical_cross_family_route() -> None:
    """Both callers build their URL from this, so it must be the /forecast route.

    It previously exposed only `inference_path` — the legacy family-specific
    endpoint the contract replaced — while both real callers hand-built the
    canonical path independently.
    """
    assert require(TINY).forecast_path == "/forecast/v1/chronos/forecast"
    assert require(TIMESFM).forecast_path == "/forecast/v1/timesfm20/forecast"


def test_legacy_inference_path_still_resolves() -> None:
    assert require(TINY).legacy_inference_path == "/forecast/v1/chronos/inference"
    assert require(TIMESFM).legacy_inference_path == "/forecast/v1/timesfm20/inference"


def test_base_url_is_overridable_per_deployment(monkeypatch) -> None:
    """Topology must not be a hardcoded literal (§3.5)."""
    monkeypatch.setenv("FORECAST_BASE_URL_TEMPLATE", "https://{container}.svc.internal:{port}")
    assert require(TINY).base_url == "https://forecast-chronos-t5-tiny.svc.internal:8000"


def test_by_id_returns_none_for_unknown() -> None:
    assert by_id("acme/nope") is None


def test_require_raises_for_unknown_and_names_the_alternatives() -> None:
    with pytest.raises(UnknownModelError) as exc:
        require("acme/nope")
    assert TINY in str(exc.value)


def test_require_rejects_a_model_marked_broken(monkeypatch) -> None:
    import dataclasses

    broken = dataclasses.replace(require(TINY), status="broken")
    monkeypatch.setattr("shared.model_registry.WORKING_MODELS", [broken])
    with pytest.raises(UnknownModelError, match="broken"):
        require(TINY)


def test_by_family_partitions_the_registry() -> None:
    chronos = by_family(ModelFamily.CHRONOS)
    timesfm = by_family(ModelFamily.TIMESFM)
    assert len(chronos) + len(timesfm) == len(WORKING_MODELS)
    assert all(m.family is ModelFamily.CHRONOS for m in chronos)


def test_as_dicts_is_json_safe() -> None:
    import json

    payload = as_dicts()
    json.dumps(payload)  # must not raise on the enum
    assert all(isinstance(d["family"], str) for d in payload)
    assert all("base_url" in d for d in payload)


def test_forecast_package_reads_the_shared_registry() -> None:
    """The forecast service must not grow a second registry again.

    It previously had one: nine models on ports that no longer existed, served
    by GET /models while the documented file was imported by nothing.
    """
    from forecast.models import get_all_models_info, get_available_models

    assert set(get_available_models()) == {m.model_id for m in WORKING_MODELS if m.is_working}
    served = get_all_models_info()
    assert set(served) == {m.model_id for m in WORKING_MODELS}
    for model in WORKING_MODELS:
        assert served[model.model_id]["port"] == model.port
