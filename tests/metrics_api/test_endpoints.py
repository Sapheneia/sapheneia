"""
Tests for Metrics API Endpoints

Tests the REST API endpoints in metrics-api/routes/endpoints.py
"""
import pytest
from fastapi.testclient import TestClient
from metrics_api.main import app

client = TestClient(app)


# --- Root & Health Endpoints ---

def test_root_endpoint():
    """Test root endpoint returns API information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Sapheneia Metrics API"
    assert data["version"] == "2.0.0"
    assert data["status"] == "operational"


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "metrics-api"


# --- Performance Metrics Endpoint ---

def test_calculate_performance_metrics_success():
    """Test full performance metrics endpoint with valid data."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "risk_free_rate": 0.0,
        "periods_per_year": 252,
        "include_interpretation": True
    }

    response = client.post("/api/v1/metrics/performance", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "sharpe_ratio" in data
    assert "max_drawdown" in data
    assert "cagr" in data
    assert "calmar_ratio" in data
    assert "win_rate" in data
    assert "interpretation" in data
    assert "metadata" in data

    # Check metadata
    assert data["metadata"]["risk_free_rate"] == 0.0
    assert data["metadata"]["periods_per_year"] == 252
    assert data["metadata"]["total_periods"] == 5


def test_calculate_performance_metrics_without_interpretation():
    """Test performance metrics without interpretation."""
    payload = {
        "returns": [0.01, 0.02, 0.015],
        "risk_free_rate": 0.0,
        "periods_per_year": 252,
        "include_interpretation": False
    }

    response = client.post("/api/v1/metrics/performance", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "sharpe_ratio" in data
    assert "interpretation" not in data


def test_calculate_performance_metrics_with_int_risk_free_rate():
    """Test performance metrics with integer risk-free rate."""
    payload = {
        "returns": [0.01, 0.02, 0.015],
        "risk_free_rate": 0,  # int
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/performance", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["risk_free_rate"] == 0


def test_calculate_performance_metrics_with_float_risk_free_rate():
    """Test performance metrics with float risk-free rate."""
    payload = {
        "returns": [0.01, 0.02, 0.015],
        "risk_free_rate": 0.04,  # float
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/performance", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["risk_free_rate"] == 0.04


def test_calculate_performance_metrics_with_list_risk_free_rate():
    """Test performance metrics with time-varying risk-free rates (list)."""
    payload = {
        "returns": [0.01, 0.02, 0.015],
        "risk_free_rate": [0.02, 0.025, 0.03],  # list
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/performance", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["risk_free_rate"] == [0.02, 0.025, 0.03]


def test_calculate_performance_metrics_empty_returns():
    """Test error handling with empty returns."""
    payload = {
        "returns": [],  # Empty
    }

    response = client.post("/api/v1/metrics/performance", json=payload)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_calculate_performance_metrics_insufficient_data():
    """Test error handling with insufficient data."""
    payload = {
        "returns": [0.01],  # Only one return
    }

    response = client.post("/api/v1/metrics/performance", json=payload)
    assert response.status_code == 400
    assert "at least 2" in response.json()["detail"].lower()


# --- Sharpe Ratio Endpoint ---

def test_calculate_sharpe_ratio_success():
    """Test Sharpe ratio endpoint with valid data."""
    payload = {
        "returns": [0.01, 0.02, 0.015],
        "risk_free_rate": 0.0,
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/sharpe", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "sharpe_ratio" in data
    assert isinstance(data["sharpe_ratio"], float)


def test_calculate_sharpe_ratio_with_int_rf():
    """Test Sharpe ratio with integer risk-free rate."""
    payload = {
        "returns": [0.01, 0.02, 0.015],
        "risk_free_rate": 0,  # int
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/sharpe", json=payload)
    assert response.status_code == 200
    assert "sharpe_ratio" in response.json()


def test_calculate_sharpe_ratio_with_list_rf():
    """Test Sharpe ratio with time-varying risk-free rates."""
    payload = {
        "returns": [0.01, 0.02, 0.015],
        "risk_free_rate": [0.02, 0.025, 0.03],  # list
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/sharpe", json=payload)
    assert response.status_code == 200
    assert "sharpe_ratio" in response.json()


# --- Maximum Drawdown Endpoint ---

def test_calculate_max_drawdown_success():
    """Test max drawdown endpoint with valid data."""
    returns = [0.01, 0.02, -0.05, 0.03, 0.01]

    response = client.post("/api/v1/metrics/max-drawdown", json=returns)
    assert response.status_code == 200
    data = response.json()
    assert "max_drawdown" in data
    assert data["max_drawdown"] <= 0  # Should be negative or zero


def test_calculate_max_drawdown_all_positive():
    """Test max drawdown with all positive returns."""
    returns = [0.01, 0.02, 0.03]

    response = client.post("/api/v1/metrics/max-drawdown", json=returns)
    assert response.status_code == 200
    data = response.json()
    assert data["max_drawdown"] == 0.0


# --- CAGR Endpoint ---

def test_calculate_cagr_success():
    """Test CAGR endpoint with valid data."""
    payload = {
        "returns": [0.01, 0.02, 0.015, 0.02],
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/cagr", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "cagr" in data
    assert isinstance(data["cagr"], float)


def test_calculate_cagr_weekly_data():
    """Test CAGR with weekly data."""
    payload = {
        "returns": [0.02, 0.015, 0.01, 0.025],
        "periods_per_year": 52  # Weekly
    }

    response = client.post("/api/v1/metrics/cagr", json=payload)
    assert response.status_code == 200
    assert "cagr" in response.json()


# --- Calmar Ratio Endpoint ---

def test_calculate_calmar_ratio_success():
    """Test Calmar ratio endpoint with valid data."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/calmar", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "calmar_ratio" in data
    assert isinstance(data["calmar_ratio"], float)


# --- Win Rate Endpoint ---

def test_calculate_win_rate_success():
    """Test win rate endpoint with valid data."""
    returns = [0.01, -0.02, 0.03, 0.02, -0.01]

    response = client.post("/api/v1/metrics/win-rate", json=returns)
    assert response.status_code == 200
    data = response.json()
    assert "win_rate" in data
    assert 0 <= data["win_rate"] <= 1


def test_calculate_win_rate_all_winners():
    """Test win rate with all positive returns."""
    returns = [0.01, 0.02, 0.03]

    response = client.post("/api/v1/metrics/win-rate", json=returns)
    assert response.status_code == 200
    data = response.json()
    assert data["win_rate"] == 1.0


def test_calculate_win_rate_all_losers():
    """Test win rate with all negative returns."""
    returns = [-0.01, -0.02, -0.03]

    response = client.post("/api/v1/metrics/win-rate", json=returns)
    assert response.status_code == 200
    data = response.json()
    assert data["win_rate"] == 0.0


# --- Error Handling ---

def test_invalid_json():
    """Test error handling with invalid JSON."""
    response = client.post(
        "/api/v1/metrics/performance",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422  # Unprocessable Entity


def test_missing_required_field():
    """Test error handling with missing required field."""
    payload = {
        # Missing 'returns' field
        "risk_free_rate": 0.0
    }

    response = client.post("/api/v1/metrics/performance", json=payload)
    assert response.status_code == 422  # Validation error


# --- All Metrics Endpoint ---

def test_calculate_all_metrics_success():
    """Test /all endpoint that calculates all metrics at once."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/all", json=payload)
    assert response.status_code == 200

    data = response.json()
    # Verify all 5 metrics are present
    assert "sharpe_ratio" in data
    assert "max_drawdown" in data
    assert "cagr" in data
    assert "calmar_ratio" in data
    assert "win_rate" in data

    # Verify all values are numeric
    assert isinstance(data["sharpe_ratio"], float)
    assert isinstance(data["max_drawdown"], float)
    assert isinstance(data["cagr"], float)
    assert isinstance(data["calmar_ratio"], float)
    assert isinstance(data["win_rate"], float)

    # Verify no extra fields (no interpretation, no metadata)
    assert len(data) == 5
    assert "interpretation" not in data
    assert "metadata" not in data


def test_calculate_all_metrics_default_example():
    """Test /all endpoint with the default documentation example."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/all", json=payload)
    assert response.status_code == 200

    data = response.json()
    # Win rate should be 60% (3 out of 5 positive)
    assert data["win_rate"] == 0.6
    # Max drawdown should be negative
    assert data["max_drawdown"] < 0


def test_calculate_all_metrics_weekly_data():
    """Test /all endpoint with weekly periodicity."""
    payload = {
        "returns": [0.02, -0.01, 0.015, 0.01, 0.025],  # Include negative return to avoid div/0
        "periods_per_year": 52  # Weekly
    }

    response = client.post("/api/v1/metrics/all", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert all(key in data for key in ["sharpe_ratio", "max_drawdown", "cagr", "calmar_ratio", "win_rate"])


def test_calculate_all_metrics_empty_returns():
    """Test /all endpoint with empty returns."""
    payload = {
        "returns": [],
        "periods_per_year": 252
    }

    response = client.post("/api/v1/metrics/all", json=payload)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
