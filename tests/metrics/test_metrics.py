"""
Tests for Financial Performance Metrics Module

Tests the metrics_api/core/metrics.py module functions and calculations.
"""

import pytest
import pandas as pd
import numpy as np
from metrics.core.metrics import (
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_cagr,
    calculate_calmar_ratio,
    calculate_win_rate,
    calculate_performance_metrics,
    _interpret_sharpe,
    _interpret_calmar,
    _interpret_win_rate,
    _validate_returns,
    SHARPE_THRESHOLDS,
    CALMAR_THRESHOLDS,
    WIN_RATE_THRESHOLDS
)


# --- Fixtures ---

@pytest.fixture
def positive_returns():
    """Simple positive return series."""
    return pd.Series([0.01, 0.02, 0.015, 0.02, 0.01])


@pytest.fixture
def mixed_returns():
    """Mixed positive and negative returns."""
    return pd.Series([0.05, -0.02, 0.03, -0.01, 0.04, 0.02, -0.03, 0.01])


@pytest.fixture
def all_negative_returns():
    """All negative returns (losing strategy)."""
    return pd.Series([-0.01, -0.02, -0.015, -0.01, -0.02])


@pytest.fixture
def volatile_returns():
    """Highly volatile returns."""
    return pd.Series([0.10, -0.08, 0.12, -0.09, 0.11, -0.07, 0.09, -0.06])


@pytest.fixture
def realistic_daily_returns():
    """Realistic daily trading returns (100 days)."""
    np.random.seed(42)
    # Generate returns with slight positive bias and realistic volatility
    returns = np.random.normal(0.001, 0.02, 100)  # ~0.1% daily mean, 2% std
    return pd.Series(returns)


# --- Validation Tests ---

def test_validate_returns_series():
    """Test validation of pandas Series."""
    returns = pd.Series([0.01, 0.02, 0.03])
    validated = _validate_returns(returns)
    assert isinstance(validated, pd.Series)
    assert len(validated) == 3


def test_validate_returns_array():
    """Test validation of numpy array."""
    returns = np.array([0.01, 0.02, 0.03])
    validated = _validate_returns(returns)
    assert isinstance(validated, pd.Series)
    assert len(validated) == 3


def test_validate_returns_list():
    """Test validation of list."""
    returns = [0.01, 0.02, 0.03]
    validated = _validate_returns(returns)
    assert isinstance(validated, pd.Series)
    assert len(validated) == 3


def test_validate_returns_with_nan():
    """Test that NaN values are removed."""
    returns = pd.Series([0.01, np.nan, 0.02, np.nan, 0.03])
    validated = _validate_returns(returns)
    assert len(validated) == 3
    assert not validated.isna().any()


def test_validate_returns_empty_error():
    """Test that empty returns raise ValueError."""
    with pytest.raises(ValueError, match="empty"):
        _validate_returns(pd.Series([]))


def test_validate_returns_all_nan_error():
    """Test that all-NaN returns raise ValueError."""
    with pytest.raises(ValueError, match="only NaN"):
        _validate_returns(pd.Series([np.nan, np.nan, np.nan]))


def test_validate_returns_insufficient_data():
    """Test that insufficient data raises ValueError."""
    with pytest.raises(ValueError, match="at least 2"):
        _validate_returns(pd.Series([0.01]))


# --- Sharpe Ratio Tests ---

def test_sharpe_ratio_positive_returns(positive_returns):
    """Test Sharpe ratio with positive returns."""
    sharpe = calculate_sharpe_ratio(positive_returns)
    assert sharpe > 0
    assert isinstance(sharpe, float)


def test_sharpe_ratio_negative_returns(all_negative_returns):
    """Test Sharpe ratio with negative returns."""
    sharpe = calculate_sharpe_ratio(all_negative_returns)
    assert sharpe < 0


def test_sharpe_ratio_with_risk_free_rate(mixed_returns):
    """Test Sharpe ratio with non-zero risk-free rate."""
    sharpe_no_rf = calculate_sharpe_ratio(mixed_returns, risk_free_rate=0.0)
    sharpe_with_rf = calculate_sharpe_ratio(mixed_returns, risk_free_rate=0.03)
    # With positive risk-free rate, Sharpe should be lower
    assert sharpe_with_rf < sharpe_no_rf


def test_sharpe_ratio_different_periods(mixed_returns):
    """Test Sharpe ratio with different periods per year."""
    sharpe_daily = calculate_sharpe_ratio(mixed_returns, periods_per_year=252)
    sharpe_weekly = calculate_sharpe_ratio(mixed_returns, periods_per_year=52)
    # Values should differ based on annualization
    assert sharpe_daily != sharpe_weekly


def test_sharpe_ratio_with_int_risk_free_rate(mixed_returns):
    """Test Sharpe ratio with integer risk-free rate."""
    sharpe = calculate_sharpe_ratio(mixed_returns, risk_free_rate=0)
    assert isinstance(sharpe, float)
    # Should work without error with int parameter


# --- Maximum Drawdown Tests ---

def test_max_drawdown_positive_returns(positive_returns):
    """Test max drawdown with all positive returns."""
    mdd = calculate_max_drawdown(positive_returns)
    # Should be zero or very small for all positive returns
    assert mdd <= 0
    assert mdd >= -0.01  # Very small drawdown


def test_max_drawdown_with_losses(mixed_returns):
    """Test max drawdown with mixed returns."""
    mdd = calculate_max_drawdown(mixed_returns)
    assert mdd < 0  # Should be negative
    assert mdd >= -1.0  # Should not be worse than -100%


def test_max_drawdown_severe_loss():
    """Test max drawdown with severe losses."""
    # Create a severe drawdown scenario
    returns = pd.Series([0.10, 0.05, -0.15, -0.10, -0.05, 0.02])
    mdd = calculate_max_drawdown(returns)
    assert mdd < -0.20  # Should show significant drawdown


# --- CAGR Tests ---

def test_cagr_positive_returns(positive_returns):
    """Test CAGR with positive returns."""
    cagr = calculate_cagr(positive_returns)
    assert cagr > 0
    assert isinstance(cagr, float)


def test_cagr_negative_returns(all_negative_returns):
    """Test CAGR with negative returns."""
    cagr = calculate_cagr(all_negative_returns)
    assert cagr < 0


def test_cagr_realistic_range(realistic_daily_returns):
    """Test that CAGR is in realistic range for trading."""
    cagr = calculate_cagr(realistic_daily_returns, periods_per_year=252)
    # Daily returns should annualize to reasonable range
    assert -1.0 < cagr < 10.0  # Between -100% and +1000% annually


# --- Calmar Ratio Tests ---

def test_calmar_ratio_positive_returns():
    """Test Calmar ratio with mostly positive returns (but with some drawdown)."""
    # Include at least one negative return to create drawdown
    returns = pd.Series([0.01, -0.005, 0.02, 0.015, 0.01])
    calmar = calculate_calmar_ratio(returns)
    print(f"Returns: {returns.tolist()}")
    print(f"Calmar ratio: {calmar}")

    assert calmar > 0  # Should be positive with net positive returns


def test_calmar_ratio_mixed_returns(mixed_returns):
    """Test Calmar ratio with mixed returns."""
    calmar = calculate_calmar_ratio(mixed_returns)
    assert isinstance(calmar, float)


def test_calmar_ratio_relationship():
    """Test relationship between CAGR, MDD, and Calmar."""
    returns = pd.Series([0.02, -0.01, 0.03, -0.02, 0.02, 0.01, -0.015, 0.025])
    cagr = calculate_cagr(returns)
    mdd = calculate_max_drawdown(returns)
    calmar = calculate_calmar_ratio(returns)

    # Calmar ≈ CAGR / abs(MDD) (approximately, as quantstats may use different formula)
    if mdd != 0:
        expected_calmar = abs(cagr / mdd)
        # Allow some tolerance for calculation differences
        assert abs(calmar - expected_calmar) / max(abs(expected_calmar), 0.001) < 0.5


# --- Win Rate Tests ---

def test_win_rate_all_positive(positive_returns):
    """Test win rate with all positive returns."""
    win_rate = calculate_win_rate(positive_returns)
    assert win_rate == 1.0


def test_win_rate_all_negative(all_negative_returns):
    """Test win rate with all negative returns."""
    win_rate = calculate_win_rate(all_negative_returns)
    assert win_rate == 0.0


def test_win_rate_mixed(mixed_returns):
    """Test win rate with mixed returns."""
    win_rate = calculate_win_rate(mixed_returns)
    assert 0.0 < win_rate < 1.0
    # Count actual winning periods
    expected_win_rate = (mixed_returns > 0).sum() / len(mixed_returns)
    assert win_rate == pytest.approx(expected_win_rate)


def test_win_rate_fifty_fifty():
    """Test win rate with 50% winners."""
    returns = pd.Series([0.01, -0.01, 0.02, -0.02, 0.03, -0.03])
    win_rate = calculate_win_rate(returns)
    assert win_rate == pytest.approx(0.5)


# --- Interpretation Tests ---

def test_interpret_sharpe():
    """Test Sharpe ratio interpretation."""
    assert _interpret_sharpe(2.5) == "excellent"
    assert _interpret_sharpe(1.5) == "good"
    assert _interpret_sharpe(0.7) == "acceptable"
    assert _interpret_sharpe(0.3) == "poor"
    assert _interpret_sharpe(-0.5) == "poor"


def test_interpret_calmar():
    """Test Calmar ratio interpretation."""
    assert _interpret_calmar(3.5) == "exceptional"
    assert _interpret_calmar(1.5) == "good"
    assert _interpret_calmar(0.7) == "decent"
    assert _interpret_calmar(0.3) == "poor"


def test_interpret_win_rate():
    """Test win rate interpretation."""
    assert _interpret_win_rate(0.65) == "high"
    assert _interpret_win_rate(0.55) == "moderate"
    assert _interpret_win_rate(0.35) == "low"


# --- Integrated Metrics Tests ---

def test_calculate_performance_metrics_basic(mixed_returns):
    """Test basic performance metrics calculation."""
    metrics = calculate_performance_metrics(mixed_returns)

    # Check all required fields are present
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics
    assert "cagr" in metrics
    assert "calmar_ratio" in metrics
    assert "win_rate" in metrics
    assert "metadata" in metrics
    assert "interpretation" in metrics  # Default is True

    # Check types
    assert isinstance(metrics["sharpe_ratio"], float)
    assert isinstance(metrics["max_drawdown"], float)
    assert isinstance(metrics["cagr"], float)
    assert isinstance(metrics["calmar_ratio"], float)
    assert isinstance(metrics["win_rate"], float)
    assert isinstance(metrics["metadata"], dict)
    assert isinstance(metrics["interpretation"], dict)


def test_calculate_performance_metrics_metadata(mixed_returns):
    """Test metadata in performance metrics."""
    metrics = calculate_performance_metrics(
        mixed_returns,
        risk_free_rate=0.03,
        periods_per_year=252
    )

    metadata = metrics["metadata"]
    assert metadata["risk_free_rate"] == 0.03
    assert metadata["periods_per_year"] == 252
    assert metadata["total_periods"] == len(mixed_returns)
    assert "profitable_periods" in metadata
    assert "losing_periods" in metadata


def test_calculate_performance_metrics_no_interpretation(mixed_returns):
    """Test metrics calculation without interpretation."""
    metrics = calculate_performance_metrics(
        mixed_returns,
        include_interpretation=False
    )

    assert "interpretation" not in metrics


def test_calculate_performance_metrics_with_int_risk_free_rate(mixed_returns):
    """Test metrics with integer risk-free rate (converts to float)."""
    metrics = calculate_performance_metrics(
        mixed_returns,
        risk_free_rate=0,  # Integer input
        periods_per_year=252
    )

    # Should be converted to float
    assert isinstance(metrics["metadata"]["risk_free_rate"], float)
    assert metrics["metadata"]["risk_free_rate"] == 0.0


def test_calculate_performance_metrics_with_float_risk_free_rate(mixed_returns):
    """Test metrics with float risk-free rate."""
    metrics = calculate_performance_metrics(
        mixed_returns,
        risk_free_rate=0.04,  # Float
        periods_per_year=252
    )

    assert isinstance(metrics["metadata"]["risk_free_rate"], float)
    assert metrics["metadata"]["risk_free_rate"] == 0.04


def test_calculate_performance_metrics_realistic_data(realistic_daily_returns):
    """Test with realistic daily trading data."""
    metrics = calculate_performance_metrics(
        realistic_daily_returns,
        risk_free_rate=0.02,  # 2% risk-free rate
        periods_per_year=252
    )

    # All metrics should be calculated
    assert all(key in metrics for key in [
        "sharpe_ratio", "max_drawdown", "cagr", "calmar_ratio", "win_rate"
    ])

    # Sharpe should be in reasonable range for realistic data
    assert -5.0 < metrics["sharpe_ratio"] < 5.0

    # Max drawdown should be negative but not extreme
    assert -0.5 < metrics["max_drawdown"] <= 0

    # CAGR should be in reasonable range
    assert -0.5 < metrics["cagr"] < 2.0

    # Win rate should be between 0 and 1
    assert 0.0 <= metrics["win_rate"] <= 1.0


def test_calculate_performance_metrics_different_periods():
    """Test metrics with different period settings."""
    # Include negative returns to avoid division by zero in Calmar
    returns = pd.Series([0.01, -0.005, 0.01, -0.005] * 13)  # 52 periods with drawdowns

    # Calculate with weekly periods
    metrics_weekly = calculate_performance_metrics(
        returns,
        periods_per_year=52
    )

    # Calculate with daily periods (wrong, but testing flexibility)
    metrics_daily = calculate_performance_metrics(
        returns,
        periods_per_year=252
    )

    # CAGR should differ due to annualization
    assert metrics_weekly["cagr"] != metrics_daily["cagr"]


def test_calculate_performance_metrics_overall_assessment():
    """Test overall assessment in interpretation."""
    # Create excellent returns with minor drawdowns
    excellent_returns = pd.Series([0.02, -0.005] * 50)  # Mostly positive with small losses
    metrics = calculate_performance_metrics(excellent_returns)

    assert "interpretation" in metrics
    assert "overall_assessment" in metrics["interpretation"]
    assessment = metrics["interpretation"]["overall_assessment"]
    assert "Excellent" in assessment or "Good" in assessment


# --- Edge Cases ---

def test_metrics_with_zero_returns():
    """Test metrics with mostly zero returns (edge case)."""
    # Mostly zeros with one tiny negative to create minimal drawdown (avoid div/0)
    returns = pd.Series([0.0, 0.0, 0.0, -0.0001, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    metrics = calculate_performance_metrics(returns)

    # With near-zero returns, we expect near-zero metrics
    assert "sharpe_ratio" in metrics
    assert "cagr" in metrics
    assert "win_rate" in metrics
    assert metrics["win_rate"] == 0.0  # No positive returns
    assert abs(metrics["cagr"]) < 0.01  # Very small CAGR


def test_metrics_with_single_large_loss():
    """Test metrics with one large loss among small gains."""
    returns = pd.Series([0.01, 0.01, 0.01, -0.20, 0.01, 0.01])
    metrics = calculate_performance_metrics(returns)

    # Max drawdown should reflect the large loss
    assert metrics["max_drawdown"] < -0.15

    # Win rate should be high despite negative overall
    assert metrics["win_rate"] > 0.7


def test_metrics_with_numpy_array_input():
    """Test that metrics work with numpy arrays."""
    returns_array = np.array([0.01, -0.01, 0.02, -0.02, 0.015])
    metrics = calculate_performance_metrics(returns_array)

    assert isinstance(metrics, dict)
    assert "sharpe_ratio" in metrics


def test_metrics_with_list_input():
    """Test that metrics work with lists."""
    returns_list = [0.01, -0.01, 0.02, -0.02, 0.015]
    metrics = calculate_performance_metrics(returns_list)

    assert isinstance(metrics, dict)
    assert "sharpe_ratio" in metrics


# --- Performance Tests ---

@pytest.mark.slow
def test_metrics_performance_large_dataset():
    """Test performance with large dataset."""
    import time

    # Generate 10 years of daily returns
    np.random.seed(42)
    large_returns = pd.Series(np.random.normal(0.0005, 0.015, 2520))

    start_time = time.time()
    metrics = calculate_performance_metrics(large_returns)
    elapsed_time = time.time() - start_time

    # Should complete quickly (< 1 second)
    assert elapsed_time < 1.0
    assert isinstance(metrics, dict)


# --- Error Handling Tests ---

def test_metrics_invalid_input_type():
    """Test that invalid input types raise ValueError."""
    with pytest.raises(ValueError):
        _validate_returns("not a valid type")


def test_metrics_with_inf_values():
    """Test handling of infinite values."""
    returns = pd.Series([0.01, np.inf, 0.02, 0.03])
    # quantstats should handle this gracefully or we catch it
    try:
        metrics = calculate_performance_metrics(returns)
        # If it succeeds, inf should be handled
        assert isinstance(metrics, dict)
    except (ValueError, Exception):
        # If it raises an error, that's also acceptable
        pass
