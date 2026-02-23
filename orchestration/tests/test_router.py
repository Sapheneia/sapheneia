"""
Tests for orchestration/router.py

Tests router endpoints via FastAPI TestClient.
The router is imported directly (not via forecast/main.py) to avoid
dependency on the chronos module.
"""

import pytest
from unittest.mock import patch, Mock
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestration.router import router
from shared.errors import register_error_handlers


@pytest.fixture
def app():
    """Create a test FastAPI app with the orchestration router."""
    test_app = FastAPI()
    register_error_handlers(test_app)
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


# =============================================================================
# Health & Models Endpoints
# =============================================================================

class TestHealthEndpoint:
    """Tests for /orchestration/v1/health."""

    def test_health_returns_200(self, client):
        resp = client.get("/orchestration/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "orchestration"


class TestModelsEndpoint:
    """Tests for /orchestration/v1/models."""

    def test_list_models_returns_families(self, client):
        resp = client.get("/orchestration/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        families = [m["family"] for m in data["models"]]
        assert "chronos" in families
        assert "timesfm" in families
        assert "moirai" in families


# =============================================================================
# Strategy Endpoints
# =============================================================================

class TestGetStrategy:
    """Tests for /orchestration/v1/strategies/{name}."""

    def test_name_with_dots_rejected(self, client):
        """Strategy names with dots (potential traversal) should return 400."""
        resp = client.get("/orchestration/v1/strategies/test.config")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "VALIDATION_ERROR"

    def test_name_with_spaces_rejected(self, client):
        """Strategy names with spaces should be rejected."""
        resp = client.get("/orchestration/v1/strategies/test%20config")
        assert resp.status_code == 400

    def test_valid_name_not_found(self, client):
        """Valid name but nonexistent strategy should return 404."""
        with patch("orchestration.router.STRATEGIES_DIR", Path("/nonexistent")):
            resp = client.get("/orchestration/v1/strategies/does_not_exist")
            assert resp.status_code == 404

    def test_valid_strategy_loaded(self, client, tmp_path):
        """Valid strategy should be loaded and returned as JSON."""
        strategy_dir = tmp_path / "strategies"
        strategy_dir.mkdir()
        (strategy_dir / "test_strat.yaml").write_text(
            "metadata:\n  id: test_strat\n  version: '1.0'\n"
        )

        with patch("orchestration.router.STRATEGIES_DIR", strategy_dir):
            resp = client.get("/orchestration/v1/strategies/test_strat")
            assert resp.status_code == 200
            data = resp.json()
            assert data["metadata"]["id"] == "test_strat"


class TestListStrategies:
    """Tests for /orchestration/v1/strategies."""

    def test_list_strategies_empty_dir(self, client, tmp_path):
        """Empty strategies dir should return empty list."""
        empty_dir = tmp_path / "strategies"
        empty_dir.mkdir()

        with patch("orchestration.router.STRATEGIES_DIR", empty_dir):
            resp = client.get("/orchestration/v1/strategies")
            assert resp.status_code == 200
            assert resp.json() == {"strategies": []}

    def test_list_strategies_missing_dir(self, client):
        """Missing strategies dir should return empty list."""
        with patch("orchestration.router.STRATEGIES_DIR", Path("/nonexistent/dir")):
            resp = client.get("/orchestration/v1/strategies")
            assert resp.status_code == 200
            assert resp.json() == {"strategies": []}

    def test_list_strategies_with_files(self, client, tmp_path):
        """Should list yaml files by stem name."""
        strategy_dir = tmp_path / "strategies"
        strategy_dir.mkdir()
        (strategy_dir / "alpha.yaml").write_text("a: 1")
        (strategy_dir / "beta.yaml").write_text("b: 2")
        (strategy_dir / "readme.txt").write_text("not a strategy")

        with patch("orchestration.router.STRATEGIES_DIR", strategy_dir):
            resp = client.get("/orchestration/v1/strategies")
            assert resp.status_code == 200
            data = resp.json()
            assert sorted(data["strategies"]) == ["alpha", "beta"]
