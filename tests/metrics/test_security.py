"""Tests for metrics service Bearer auth."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_auth(monkeypatch):
    monkeypatch.setenv("METRICS_API_KEY", "test-token")
    # Reload so Settings picks up the env var
    from metrics.core import config, security

    importlib.reload(config)
    importlib.reload(security)
    from metrics import main

    importlib.reload(main)
    return TestClient(main.app), "test-token"


@pytest.fixture
def client_no_auth(monkeypatch):
    monkeypatch.delenv("METRICS_API_KEY", raising=False)
    from metrics.core import config, security

    importlib.reload(config)
    importlib.reload(security)
    from metrics import main

    importlib.reload(main)
    return TestClient(main.app)


def test_compute_requires_token_when_set(client_with_auth) -> None:
    client, _ = client_with_auth
    r = client.post("/metrics/v1/compute", json={"returns": [0.01, 0.02], "metric": "all"})
    assert r.status_code == 401


def test_compute_accepts_correct_token(client_with_auth) -> None:
    client, token = client_with_auth
    r = client.post(
        "/metrics/v1/compute",
        json={"returns": [0.01, 0.02], "metric": "all"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text


def test_compute_open_when_no_key_set(client_no_auth) -> None:
    r = client_no_auth.post("/metrics/v1/compute", json={"returns": [0.01, 0.02], "metric": "all"})
    assert r.status_code == 200, r.text
