"""Guard the hand-maintained tables that must agree with each other.

Adding a model means editing `shared/model_registry.py` AND `docker-compose.yml`
in step. Nothing enforced that, so a mismatch surfaced only as a connection
refusal at run time — after a sweep had already been dispatched. Same for the
TimescaleDB image tag, which is pinned in three files.
"""

from __future__ import annotations

import pathlib
import re

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPOSE = REPO_ROOT / "docker-compose.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def compose() -> dict:
    # Compose interpolates ${VAR:-default}; for structural assertions the raw
    # text is fine, we only read keys and literal values.
    return yaml.safe_load(COMPOSE.read_text())


@pytest.fixture(scope="module")
def forecast_services(compose) -> dict[str, dict]:
    return {name: svc for name, svc in compose["services"].items() if name.startswith("forecast-")}


def test_every_registry_model_has_a_compose_service(compose, forecast_services) -> None:
    from shared.model_registry import WORKING_MODELS

    for model in WORKING_MODELS:
        assert model.container in compose["services"], (
            f"{model.model_id} points at container {model.container!r}, "
            "which has no docker-compose service"
        )


def test_every_registry_model_is_pinned_by_model_variant(compose) -> None:
    """The canonical /forecast route refuses to serve an unpinned container."""
    from shared.model_registry import WORKING_MODELS

    for model in WORKING_MODELS:
        env = compose["services"][model.container].get("environment") or {}
        assert env.get("MODEL_VARIANT") == model.model_id, (
            f"{model.container} must set MODEL_VARIANT={model.model_id!r}, "
            f"got {env.get('MODEL_VARIANT')!r}"
        )


def test_registry_ports_match_compose_publishes(compose) -> None:
    from shared.model_registry import WORKING_MODELS

    for model in WORKING_MODELS:
        ports = compose["services"][model.container].get("ports") or []
        joined = " ".join(str(p) for p in ports)
        assert str(model.port) in joined, (
            f"{model.container} publishes {joined!r}, registry says port {model.port}"
        )


def test_no_forecast_service_is_missing_from_the_registry(forecast_services) -> None:
    """A compose service with no registry row is unroutable by the orchestrator."""
    from shared.model_registry import WORKING_MODELS

    known = {m.container for m in WORKING_MODELS}
    for name in forecast_services:
        assert name in known, f"compose defines {name!r} but no registry row routes to it"


def test_timescaledb_image_pin_is_identical_everywhere() -> None:
    from conftest import TIMESCALEDB_IMAGE

    pattern = re.compile(r"timescale/timescaledb:[\w.\-]+")
    for path in (COMPOSE, CI_WORKFLOW):
        found = set(pattern.findall(path.read_text()))
        assert found, f"no TimescaleDB image pin found in {path.name}"
        assert found == {TIMESCALEDB_IMAGE}, (
            f"{path.name} pins {found}, conftest.TIMESCALEDB_IMAGE is {TIMESCALEDB_IMAGE!r}"
        )


def test_no_service_image_uses_a_floating_tag(compose) -> None:
    for name, svc in compose["services"].items():
        image = svc.get("image")
        if not image:
            continue
        assert ":" in image, f"{name} image {image!r} has no tag"
        tag = image.rsplit(":", 1)[1]
        assert tag != "latest" and not tag.startswith("latest-"), (
            f"{name} uses floating tag {tag!r}"
        )
