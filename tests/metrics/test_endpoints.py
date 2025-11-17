"""
Tests for Metrics API Endpoints

Tests the unified /metrics/v1/compute/ endpoint with different metric parameters.
"""
import pytest
from fastapi.testclient import TestClient


# --- Basic Endpoints Tests ---

def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Sapheneia Metrics API"
    assert data["version"] == "2.0.0"
    assert "compute" in data["endpoints"]


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "metrics"


# --- Compute Endpoint: metric="performance" ---

def test_compute_performance_with_interpretation(client):
    """Test compute endpoint with metric='performance' and interpretation."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "performance",
        "risk_free_rate": 0.0,
        "periods_per_year": 252,
        "include_interpretation": True
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "sharpe_ratio" in data
    assert "max_drawdown" in data
    assert "cagr" in data
    assert "calmar_ratio" in data
    assert "win_rate" in data
    assert "interpretation" in data
    assert "metadata" in data
    assert data["metadata"]["periods_per_year"] == 252
    assert data["metadata"]["total_periods"] == 5


def test_compute_performance_without_interpretation(client):
    """Test compute endpoint with metric='performance' without interpretation."""
    payload = {
        "returns": [0.01, -0.005, 0.02, 0.015],
        "metric": "performance",
        "risk_free_rate": 0.0,
        "periods_per_year": 252,
        "include_interpretation": False
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "sharpe_ratio" in data
    assert "interpretation" not in data


def test_compute_performance_with_risk_free_rate(client):
    """Test compute endpoint with non-zero risk-free rate."""
    payload = {
        "returns": [0.01, -0.005, 0.02, 0.015],
        "metric": "performance",
        "risk_free_rate": 0.04,
        "periods_per_year": 252
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["risk_free_rate"] == 0.04


# --- Compute Endpoint: metric="all" ---

def test_compute_all_metrics(client):
    """Test compute endpoint with metric='all'."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "all",
        "periods_per_year": 252
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200

    data = response.json()
    # Should have all 5 metrics
    assert "sharpe_ratio" in data
    assert "max_drawdown" in data
    assert "cagr" in data
    assert "calmar_ratio" in data
    assert "win_rate" in data
    # Should NOT have interpretation or metadata
    assert "interpretation" not in data
    assert "metadata" not in data
    # Verify it's clean response
    assert len(data) == 5


def test_compute_all_default_example(client):
    """Test compute all with the standard example vector."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "all"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    assert data["win_rate"] == 0.6


def test_compute_all_weekly_data(client):
    """Test compute all with weekly data."""
    payload = {
        "returns": [0.02, -0.01, 0.015, 0.01, 0.025],
        "metric": "all",
        "periods_per_year": 52
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    assert len(response.json()) == 5


# --- Compute Endpoint: Individual Metrics ---

def test_compute_sharpe_only(client):
    """Test compute endpoint with metric='sharpe'."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "sharpe",
        "risk_free_rate": 0.0,
        "periods_per_year": 252
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "sharpe_ratio" in data
    assert len(data) == 1


def test_compute_sharpe_with_risk_free_rate(client):
    """Test Sharpe ratio with non-zero risk-free rate."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "sharpe",
        "risk_free_rate": 0.04,
        "periods_per_year": 252
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    assert "sharpe_ratio" in response.json()


def test_compute_max_drawdown_only(client):
    """Test compute endpoint with metric='max_drawdown'."""
    payload = {
        "returns": [0.01, 0.02, -0.05, 0.03, 0.01],
        "metric": "max_drawdown"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "max_drawdown" in data
    assert data["max_drawdown"] <= 0  # Should be negative or zero
    assert len(data) == 1


def test_compute_cagr_only(client):
    """Test compute endpoint with metric='cagr'."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "cagr",
        "periods_per_year": 252
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "cagr" in data
    assert len(data) == 1


def test_compute_cagr_weekly_data(client):
    """Test CAGR with weekly data."""
    payload = {
        "returns": [0.02, -0.01, 0.015, 0.01, 0.025],
        "metric": "cagr",
        "periods_per_year": 52
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    assert "cagr" in response.json()


def test_compute_calmar_only(client):
    """Test compute endpoint with metric='calmar'."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "calmar",
        "periods_per_year": 252
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "calmar_ratio" in data
    assert len(data) == 1


def test_compute_win_rate_only(client):
    """Test compute endpoint with metric='win_rate'."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "win_rate"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "win_rate" in data
    assert data["win_rate"] == 0.6
    assert len(data) == 1


def test_compute_win_rate_all_winners(client):
    """Test win rate with all positive returns."""
    payload = {
        "returns": [0.01, 0.02, 0.03],
        "metric": "win_rate"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["win_rate"] == 1.0


def test_compute_win_rate_all_losers(client):
    """Test win rate with all negative returns."""
    payload = {
        "returns": [-0.01, -0.02, -0.03],
        "metric": "win_rate"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["win_rate"] == 0.0


# --- Error Handling ---

def test_compute_empty_returns(client):
    """Test error handling with empty returns."""
    payload = {
        "returns": [],
        "metric": "all"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_compute_insufficient_data(client):
    """Test error handling with insufficient data."""
    payload = {
        "returns": [0.01],  # Only one return
        "metric": "sharpe"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 400


def test_compute_invalid_json(client):
    """Test error handling with invalid JSON."""
    response = client.post(
        "/metrics/v1/compute/",
        data="not valid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


def test_compute_missing_required_field(client):
    """Test error handling with missing required field."""
    payload = {
        "metric": "sharpe"
        # Missing 'returns'
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 422


def test_compute_invalid_metric_type(client):
    """Test error handling with invalid metric type."""
    payload = {
        "returns": [0.01, -0.02, 0.03],
        "metric": "invalid_metric"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 422  # Pydantic validation error


# --- Default Behavior ---

def test_compute_defaults(client):
    """Test compute endpoint with default parameters."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01]
        # Using all defaults: metric='performance', risk_free_rate=0.0, etc.
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Default is 'performance' with interpretation
    assert "interpretation" in data
    assert "metadata" in data
