"""
Financial Performance Metrics Module

Provides evaluation metrics for trading strategies and forecasting performance.
Built on top of quantstats library for robust, industry-standard calculations.

Metrics included:
- Sharpe Ratio: Risk-adjusted returns (return per unit of volatility)
- Maximum Drawdown: Worst peak-to-trough decline
- CAGR: Compound Annual Growth Rate
- Calmar Ratio: Return per unit of maximum drawdown
- Win Rate: Percentage of profitable periods

Usage:
    from api.core.metrics import calculate_performance_metrics

    returns = pd.Series([0.01, -0.02, 0.03, ...])
    metrics = calculate_performance_metrics(returns)
"""

import logging
from typing import Dict, Any, Optional, Union, List
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

try:
    import quantstats as qs
    QUANTSTATS_AVAILABLE = True
except ImportError:
    QUANTSTATS_AVAILABLE = False
    logger.warning("quantstats not available. Install with: pip install quantstats")


# --- Performance Thresholds ---
# These provide interpretation guidance for metric values

SHARPE_THRESHOLDS = {
    "excellent": 2.0,
    "good": 1.0,
    "acceptable": 0.5,
    "poor": 0.0
}

CALMAR_THRESHOLDS = {
    "exceptional": 3.0,
    "good": 1.0,
    "decent": 0.5,
    "poor": 0.0
}

WIN_RATE_THRESHOLDS = {
    "high": 0.6,
    "moderate": 0.5,
    "low": 0.4
}


# --- Helper Functions ---

def _interpret_sharpe(sharpe_ratio: float) -> str:
    """Interpret Sharpe ratio value."""
    if sharpe_ratio >= SHARPE_THRESHOLDS["excellent"]:
        return "excellent"
    elif sharpe_ratio >= SHARPE_THRESHOLDS["good"]:
        return "good"
    elif sharpe_ratio >= SHARPE_THRESHOLDS["acceptable"]:
        return "acceptable"
    else:
        return "poor"


def _interpret_calmar(calmar_ratio: float) -> str:
    """Interpret Calmar ratio value."""
    if calmar_ratio >= CALMAR_THRESHOLDS["exceptional"]:
        return "exceptional"
    elif calmar_ratio >= CALMAR_THRESHOLDS["good"]:
        return "good"
    elif calmar_ratio >= CALMAR_THRESHOLDS["decent"]:
        return "decent"
    else:
        return "poor"


def _interpret_win_rate(win_rate: float) -> str:
    """Interpret win rate value."""
    if win_rate >= WIN_RATE_THRESHOLDS["high"]:
        return "high"
    elif win_rate >= WIN_RATE_THRESHOLDS["moderate"]:
        return "moderate"
    else:
        return "low"


def _validate_returns(returns: Union[pd.Series, np.ndarray, list]) -> pd.Series:
    """
    Validate and convert returns to pandas Series.

    Args:
        returns: Return values (can be Series, array, or list)

    Returns:
        Validated pandas Series

    Raises:
        ValueError: If returns are invalid
    """
    # Convert to Series if needed
    if isinstance(returns, (np.ndarray, list)):
        returns = pd.Series(returns)

    if not isinstance(returns, pd.Series):
        raise ValueError("Returns must be a pandas Series, numpy array, or list")

    # Check for empty or all-NaN
    if len(returns) == 0:
        raise ValueError("Returns series is empty")

    if returns.isna().all():
        raise ValueError("Returns series contains only NaN values")

    # Remove NaN values
    returns_clean = returns.dropna()

    if len(returns_clean) < 2:
        raise ValueError(f"Need at least 2 valid returns, got {len(returns_clean)}")

    return returns_clean


# --- Core Metrics Functions ---

def calculate_sharpe_ratio(
    returns: Union[pd.Series, np.ndarray, List],
    risk_free_rate: Union[int, float, List[float]] = 0,
    periods_per_year: int = 252
) -> float:
    """
    Calculate Sharpe Ratio: risk-adjusted return metric.

    Measures excess return per unit of volatility. Higher is better.

    Args:
        returns: Return series (e.g., daily returns)
        risk_free_rate: Annual risk-free rate (default: 0). Can be:
            - int: Single rate applied to all periods (e.g., 0 for 0%)
            - float: Single rate (e.g., 0.04 for 4%)
            - List[float]: Time-varying risk-free rates matching returns length
        periods_per_year: Number of periods per year (252 for daily, 52 for weekly, 12 for monthly)

    Returns:
        Sharpe ratio value

    Interpretation:
        > 2.0: Excellent
        > 1.0: Good
        > 0.5: Acceptable
        < 0.5: Poor
    """
    if not QUANTSTATS_AVAILABLE:
        raise ImportError("quantstats is required for metrics calculation")

    returns = _validate_returns(returns)

    try:
        sharpe = qs.stats.sharpe(returns, rf=risk_free_rate, periods=periods_per_year)
        return float(sharpe) if not np.isnan(sharpe) else 0.0
    except Exception as e:
        logger.warning(f"Error calculating Sharpe ratio: {e}")
        return 0.0


def calculate_max_drawdown(returns: Union[pd.Series, np.ndarray, List]) -> float:
    """
    Calculate Maximum Drawdown: worst peak-to-trough decline.

    Shows the largest percentage drop from a peak. Always negative or zero.
    Critical for understanding worst-case scenarios.

    Args:
        returns: Return series

    Returns:
        Maximum drawdown as negative decimal (e.g., -0.25 for 25% drawdown)

    Interpretation:
        Closer to 0: Better (less severe drawdown)
        < -0.20: Significant risk
        < -0.50: Very high risk
    """
    if not QUANTSTATS_AVAILABLE:
        raise ImportError("quantstats is required for metrics calculation")

    returns = _validate_returns(returns)

    try:
        max_dd = qs.stats.max_drawdown(returns)
        return float(max_dd) if not np.isnan(max_dd) else 0.0
    except Exception as e:
        logger.warning(f"Error calculating max drawdown: {e}")
        return 0.0


def calculate_cagr(
    returns: Union[pd.Series, np.ndarray, List],
    periods_per_year: int = 252
) -> float:
    """
    Calculate Compound Annual Growth Rate (CAGR).

    Geometric mean return, representing the annualized return rate.

    Args:
        returns: Return series
        periods_per_year: Number of periods per year

    Returns:
        CAGR as decimal (e.g., 0.15 for 15% annual return)

    Interpretation:
        Positive: Profitable
        > 0.15: Strong performance
        > 0.30: Exceptional performance
    """
    if not QUANTSTATS_AVAILABLE:
        raise ImportError("quantstats is required for metrics calculation")

    returns = _validate_returns(returns)

    try:
        cagr = qs.stats.cagr(returns, periods=periods_per_year)
        return float(cagr) if not np.isnan(cagr) else 0.0
    except Exception as e:
        logger.warning(f"Error calculating CAGR: {e}")
        return 0.0


def calculate_calmar_ratio(
    returns: Union[pd.Series, np.ndarray, List],
    periods_per_year: int = 252
) -> float:
    """
    Calculate Calmar Ratio: return per unit of maximum drawdown.

    Measures return relative to worst-case risk. Higher is better.
    Complements Sharpe by focusing on tail risk rather than volatility.

    Args:
        returns: Return series
        periods_per_year: Number of periods per year

    Returns:
        Calmar ratio value

    Interpretation:
        > 3.0: Exceptional
        > 1.0: Good
        > 0.5: Decent
        < 0.5: Poor
    """
    if not QUANTSTATS_AVAILABLE:
        raise ImportError("quantstats is required for metrics calculation")

    returns = _validate_returns(returns)

    try:
        calmar = qs.stats.calmar(returns, periods=periods_per_year)
        return float(calmar) if not np.isnan(calmar) else 0.0
    except Exception as e:
        logger.warning(f"Error calculating Calmar ratio: {e}")
        return 0.0


def calculate_win_rate(returns: Union[pd.Series, np.ndarray, List]) -> float:
    """
    Calculate Win Rate: percentage of profitable periods.

    Important for psychological sustainability and strategy intuition.
    Must be paired with profit factor to understand strategy profile.

    Args:
        returns: Return series

    Returns:
        Win rate as decimal (e.g., 0.58 for 58% win rate)

    Interpretation:
        > 0.60: High win rate
        > 0.50: Moderate win rate
        < 0.40: Low win rate (needs large winners to compensate)

    Note:
        30% win rate can be excellent if winners are much larger than losers.
    """
    returns = _validate_returns(returns)

    try:
        winning_periods = (returns > 0).sum()
        total_periods = len(returns)
        win_rate = winning_periods / total_periods if total_periods > 0 else 0.0
        return float(win_rate)
    except Exception as e:
        logger.warning(f"Error calculating win rate: {e}")
        return 0.0


# --- Main Function ---

def calculate_performance_metrics(
    returns: Union[pd.Series, np.ndarray, List],
    risk_free_rate: Union[int, float, List[float]] = 0,
    periods_per_year: int = 252,
    include_interpretation: bool = True
) -> Dict[str, Any]:
    """
    Calculate all key performance metrics for a return series.

    This is the main entry point for metrics calculation. It computes
    all five core metrics and optionally provides interpretation guidance.

    Args:
        returns: Return series (daily, weekly, or monthly returns)
        risk_free_rate: Annual risk-free rate for Sharpe calculation (default: 0). Can be:
            - int: Single rate (e.g., 0 for 0%)
            - float: Single rate (e.g., 0.04 for 4%)
            - List[float]: Time-varying risk-free rates matching returns length
        periods_per_year: Trading periods per year (252=daily, 52=weekly, 12=monthly)
        include_interpretation: Whether to include interpretation of metric values

    Returns:
        Dictionary containing:
            - sharpe_ratio: Risk-adjusted return metric
            - max_drawdown: Worst peak-to-trough decline
            - cagr: Compound annual growth rate
            - calmar_ratio: Return per unit of max drawdown
            - win_rate: Percentage of profitable periods
            - interpretation: Human-readable assessment (if include_interpretation=True)
            - metadata: Configuration used for calculation

    Raises:
        ImportError: If quantstats is not installed
        ValueError: If returns are invalid

    Example:
        >>> returns = pd.Series([0.01, -0.02, 0.03, 0.02, -0.01])
        >>> metrics = calculate_performance_metrics(returns)
        >>> print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        >>> print(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
    """
    if not QUANTSTATS_AVAILABLE:
        raise ImportError(
            "quantstats is required for metrics calculation. "
            "Install with: pip install quantstats"
        )

    # Validate returns
    returns = _validate_returns(returns)

    logger.info(f"Calculating metrics for {len(returns)} return periods")

    # Calculate all metrics
    sharpe = calculate_sharpe_ratio(returns, risk_free_rate, periods_per_year)
    max_dd = calculate_max_drawdown(returns)
    cagr = calculate_cagr(returns, periods_per_year)
    calmar = calculate_calmar_ratio(returns, periods_per_year)
    win_rate = calculate_win_rate(returns)

    # Build result
    result = {
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "cagr": cagr,
        "calmar_ratio": calmar,
        "win_rate": win_rate,
        "metadata": {
            "risk_free_rate": risk_free_rate,
            "periods_per_year": periods_per_year,
            "total_periods": len(returns),
            "profitable_periods": int((returns > 0).sum()),
            "losing_periods": int((returns < 0).sum())
        }
    }

    # Add interpretation if requested
    if include_interpretation:
        result["interpretation"] = {
            "sharpe_ratio": _interpret_sharpe(sharpe),
            "calmar_ratio": _interpret_calmar(calmar),
            "win_rate": _interpret_win_rate(win_rate),
            "overall_assessment": _get_overall_assessment(sharpe, max_dd, calmar, win_rate)
        }

    logger.info(f"Metrics calculated: Sharpe={sharpe:.2f}, MDD={max_dd:.2%}, CAGR={cagr:.2%}")

    return result


def _get_overall_assessment(
    sharpe: float,
    max_dd: float,
    calmar: float,
    win_rate: float
) -> str:
    """
    Provide overall assessment based on all metrics.

    Args:
        sharpe: Sharpe ratio
        max_dd: Maximum drawdown
        calmar: Calmar ratio
        win_rate: Win rate

    Returns:
        Overall assessment string
    """
    # Score each metric
    sharpe_score = 3 if sharpe >= 2.0 else (2 if sharpe >= 1.0 else (1 if sharpe >= 0.5 else 0))
    mdd_score = 3 if max_dd > -0.15 else (2 if max_dd > -0.25 else (1 if max_dd > -0.40 else 0))
    calmar_score = 3 if calmar >= 3.0 else (2 if calmar >= 1.0 else (1 if calmar >= 0.5 else 0))
    win_rate_score = 2 if win_rate >= 0.6 else (1 if win_rate >= 0.5 else 0)

    # Calculate total score
    total_score = sharpe_score + mdd_score + calmar_score + win_rate_score
    max_score = 11

    # Provide assessment
    if total_score >= 9:
        return "Excellent: Strong risk-adjusted returns with manageable drawdowns"
    elif total_score >= 6:
        return "Good: Solid performance with acceptable risk profile"
    elif total_score >= 3:
        return "Moderate: Acceptable but room for improvement"
    else:
        return "Poor: Significant concerns with risk-adjusted performance"
