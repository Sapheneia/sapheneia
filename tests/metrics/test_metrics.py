"""
Tests for Financial Performance Metrics Module

Tests the metrics_api/core/metrics.py module functions and calculations.
"""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from metrics.core.metrics import (
    _interpret_calmar,
    _interpret_sharpe,
    _interpret_win_rate,
    _validate_returns,
    calculate_cagr,
    calculate_calmar_ratio,
    calculate_max_drawdown,
    calculate_performance_metrics,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_total_return,
    calculate_win_rate,
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
        mixed_returns, risk_free_rate=0.03, periods_per_year=252
    )

    metadata = metrics["metadata"]
    assert metadata["risk_free_rate"] == 0.03
    assert metadata["periods_per_year"] == 252
    assert metadata["total_periods"] == len(mixed_returns)
    assert "profitable_periods" in metadata
    assert "losing_periods" in metadata


def test_calculate_performance_metrics_no_interpretation(mixed_returns):
    """Test metrics calculation without interpretation."""
    metrics = calculate_performance_metrics(mixed_returns, include_interpretation=False)

    assert "interpretation" not in metrics


def test_calculate_performance_metrics_with_int_risk_free_rate(mixed_returns):
    """Test metrics with integer risk-free rate (converts to float)."""
    metrics = calculate_performance_metrics(
        mixed_returns,
        risk_free_rate=0,  # Integer input
        periods_per_year=252,
    )

    # Should be converted to float
    assert isinstance(metrics["metadata"]["risk_free_rate"], float)
    assert metrics["metadata"]["risk_free_rate"] == 0.0


def test_calculate_performance_metrics_with_float_risk_free_rate(mixed_returns):
    """Test metrics with float risk-free rate."""
    metrics = calculate_performance_metrics(
        mixed_returns,
        risk_free_rate=0.04,  # Float
        periods_per_year=252,
    )

    assert isinstance(metrics["metadata"]["risk_free_rate"], float)
    assert metrics["metadata"]["risk_free_rate"] == 0.04


def test_calculate_performance_metrics_realistic_data(realistic_daily_returns):
    """Test with realistic daily trading data."""
    metrics = calculate_performance_metrics(
        realistic_daily_returns,
        risk_free_rate=0.02,  # 2% risk-free rate
        periods_per_year=252,
    )

    # All metrics should be calculated
    assert all(
        key in metrics
        for key in ["sharpe_ratio", "max_drawdown", "cagr", "calmar_ratio", "win_rate"]
    )

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
    metrics_weekly = calculate_performance_metrics(returns, periods_per_year=52)

    # Calculate with daily periods (wrong, but testing flexibility)
    metrics_daily = calculate_performance_metrics(returns, periods_per_year=252)

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
    """Test that Inf values are removed and metrics still compute."""
    returns = pd.Series([0.01, np.inf, 0.02, 0.03])
    metrics = calculate_performance_metrics(returns)
    assert isinstance(metrics, dict)
    assert "sharpe_ratio" in metrics
    assert not np.isinf(metrics["sharpe_ratio"])


# --- GAP-15 Edge Case Tests ---


def test_validate_returns_with_inf_removed():
    """_validate_returns should remove Inf values and continue."""
    returns = pd.Series([0.01, np.inf, 0.02, -np.inf, 0.03])
    validated = _validate_returns(returns)
    assert not np.isinf(validated).any()
    assert len(validated) == 3


def test_sharpe_ratio_exception_returns_none():
    """calculate_sharpe_ratio should return None on internal exception, not crash or fake a 0."""
    # This tests the try/except in calculate_sharpe_ratio
    with patch("metrics.core.metrics.qs.stats.sharpe", side_effect=Exception("qs error")):
        result = calculate_sharpe_ratio([0.01, 0.02, 0.03])
        assert result is None


def test_cagr_exception_returns_none():
    """calculate_cagr should return None on internal exception."""
    with patch("metrics.core.metrics.qs.stats.cagr", side_effect=Exception("qs error")):
        result = calculate_cagr([0.01, 0.02, 0.03])
        assert result is None


def test_calmar_exception_returns_none():
    """calculate_calmar_ratio should return None on internal exception."""
    with patch("metrics.core.metrics.qs.stats.calmar", side_effect=Exception("qs error")):
        result = calculate_calmar_ratio([0.01, 0.02, 0.03])
        assert result is None


def test_performance_metrics_partial_failure():
    """If one metric fails, others should still compute."""
    returns = [0.01, -0.02, 0.03, 0.02, -0.01]
    with patch("metrics.core.metrics.qs.stats.sharpe", side_effect=Exception("sharpe broke")):
        result = calculate_performance_metrics(returns)
        # Sharpe is undefined (None), the others are still computed
        assert result["sharpe_ratio"] is None
        assert result["sortino_ratio"] is not None
        assert "max_drawdown" in result
        assert "win_rate" in result
        assert result["win_rate"] > 0  # Should still work


# --- Sortino ratio and total return ---


def test_total_return_compounds():
    """Total return compounds the series rather than summing it."""
    assert calculate_total_return([0.10, 0.10]) == pytest.approx(0.21)
    assert calculate_total_return([0.10, -0.10]) == pytest.approx(-0.01)


def test_sortino_ratio_known_value():
    """Hand-derived: mean 0.006, downside deviation sqrt((0.02**2 + 0.01**2) / 5) = 0.01."""
    sortino = calculate_sortino_ratio([0.01, -0.02, 0.03, 0.02, -0.01])
    assert sortino == pytest.approx(0.6 * np.sqrt(252), rel=1e-6)


def test_sortino_ratio_mixed_returns(mixed_returns):
    """Sortino is a finite float for a series that has losing periods."""
    sortino = calculate_sortino_ratio(mixed_returns)
    assert isinstance(sortino, float)
    assert np.isfinite(sortino)


def test_sortino_ratio_no_losses_is_undefined():
    """No downside deviation means an undefined ratio (None), not a misleading 0.0."""
    assert calculate_sortino_ratio([0.01, 0.02, 0.03]) is None


def test_zero_variance_ratios_are_undefined():
    """Constant returns have no volatility: Sharpe and Calmar are None, not 0.0."""
    flat = [0.01, 0.01, 0.01]
    assert calculate_sharpe_ratio(flat) is None
    assert calculate_calmar_ratio(flat) is None


def test_returns_below_minus_one_are_rejected():
    """A period return under -100% is impossible; compounding it flips signs."""
    with pytest.raises(ValueError, match="below -1.0"):
        calculate_total_return([-2.0, 0.1])
    with pytest.raises(ValueError, match="below -1.0"):
        calculate_performance_metrics([-2.0, -3.0])


def test_total_return_total_loss_is_minus_one():
    """Exactly -100% is a valid total loss and stays -1.0."""
    assert calculate_total_return([-1.0, 0.5]) == pytest.approx(-1.0)


def test_total_return_overflow_is_undefined():
    assert calculate_total_return([1e200, 1e200]) is None


def test_performance_metrics_flag_constant_returns():
    result = calculate_performance_metrics([0.0, 0.0, 0.0, 0.0])
    assert "constant_returns" in result["warnings"]
    assert result["sharpe_ratio"] is None
    assert result["interpretation"]["sharpe_ratio"] == "undefined"
    assert result["total_return"] == 0.0


def test_performance_metrics_report_dropped_returns():
    result = calculate_performance_metrics([0.5, np.nan, 0.1, -0.2])
    assert result["metadata"]["dropped_periods"] == 1
    assert result["metadata"]["total_periods"] == 3
    assert "dropped_nonfinite_returns:1" in result["warnings"]


def test_sortino_and_max_drawdown_exceptions_return_none():
    with patch("metrics.core.metrics.qs.stats.sortino", side_effect=Exception("boom")):
        assert calculate_sortino_ratio([0.01, -0.02, 0.03]) is None
    with patch("metrics.core.metrics.qs.stats.max_drawdown", side_effect=Exception("boom")):
        assert calculate_max_drawdown([0.01, -0.02, 0.03]) is None


def test_performance_metrics_no_warnings_key_when_clean():
    # 60 periods with 24 losing ones and varied values: no caveats apply.
    clean = np.tile([0.01, -0.005, 0.02, -0.01, 0.015], 12)
    assert "warnings" not in calculate_performance_metrics(clean)


def test_performance_metrics_flag_low_sample(mixed_returns):
    # mixed_returns has 8 periods, below the 30-period reliability threshold.
    assert "low_sample:8" in calculate_performance_metrics(mixed_returns)["warnings"]


def test_performance_metrics_flag_few_losing_periods():
    # 40 periods but only 2 losers: Sortino rests on two observations.
    returns = np.array([0.01, 0.012, 0.008, 0.011] * 10)
    returns[5] = -0.004
    returns[20] = -0.006
    warnings = calculate_performance_metrics(returns)["warnings"]
    assert warnings == ["few_losing_periods:2"]


def test_no_losing_periods_warns_nothing_extra():
    # Zero losers makes Sortino undefined (None); that is not also a 'few losers' case.
    returns = np.array([0.01, 0.012, 0.008, 0.011] * 10)
    result = calculate_performance_metrics(returns)
    assert result["sortino_ratio"] is None
    assert not any(w.startswith("few_losing") for w in result.get("warnings", []))


def test_performance_metrics_include_sortino_and_total_return(mixed_returns):
    """The performance payload carries the two fields the orchestrator persists."""
    metrics = calculate_performance_metrics(mixed_returns)
    assert isinstance(metrics["sortino_ratio"], float)
    assert metrics["total_return"] == pytest.approx(0.09047173504068784)
