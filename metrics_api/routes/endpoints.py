"""
Metrics API Endpoints

REST API endpoints for financial performance metrics calculation.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from metrics_api.core import metrics

router = APIRouter(prefix="/metrics", tags=["Metrics"])


# --- Request/Response Schemas ---

class PerformanceMetricsRequest(BaseModel):
    """Request model for performance metrics calculation."""
    returns: List[float] = Field(..., description="Return series (e.g., daily returns)")
    risk_free_rate: float = Field(
        default=0.0,
        description="Annual risk-free rate (e.g., 0.04 for 4%)"
    )
    periods_per_year: int = Field(
        default=252,
        description="Trading periods per year (252=daily, 52=weekly, 12=monthly)"
    )
    include_interpretation: bool = Field(
        default=True,
        description="Include human-readable interpretation"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
                    "risk_free_rate": 0.0,
                    "periods_per_year": 252,
                    "include_interpretation": True
                }
            ]
        }
    }


class PerformanceMetricsResponse(BaseModel):
    """Response model for performance metrics."""
    sharpe_ratio: float
    max_drawdown: float
    cagr: float
    calmar_ratio: float
    win_rate: float
    interpretation: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any]

    model_config = {
        "json_schema_extra": {
            "example": {
                "sharpe_ratio": 1.23,
                "max_drawdown": -0.15,
                "cagr": 0.25,
                "calmar_ratio": 1.67,
                "win_rate": 0.6,
                "interpretation": {
                    "sharpe_ratio": "Good",
                    "calmar_ratio": "Good",
                    "win_rate": "High win rate",
                    "overall_assessment": "Good: Solid performance with acceptable risk profile"
                },
                "metadata": {
                    "risk_free_rate": 0.0,
                    "periods_per_year": 252,
                    "total_periods": 5,
                    "profitable_periods": 3,
                    "losing_periods": 1
                }
            }
        }
    }


class SharpeRatioRequest(BaseModel):
    """Request model for Sharpe ratio calculation."""
    returns: List[float]
    risk_free_rate: float = 0.0
    periods_per_year: int = 252


class MetricRequest(BaseModel):
    """Generic request model for single metric calculation."""
    returns: List[float]
    periods_per_year: int = 252


# --- Endpoints ---

@router.post("/performance", response_model=PerformanceMetricsResponse, response_model_exclude_none=True)
async def calculate_performance_metrics_endpoint(request: PerformanceMetricsRequest):
    """
    Calculate all performance metrics for a return series.

    Returns:
    - Sharpe Ratio: Risk-adjusted return metric
    - Maximum Drawdown: Worst peak-to-trough decline
    - CAGR: Compound Annual Growth Rate
    - Calmar Ratio: Return per unit of maximum drawdown
    - Win Rate: Percentage of profitable periods
    - Interpretation: Human-readable assessment (optional)

    **Example Request:**
    ```json
    {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "risk_free_rate": 0.0,
        "periods_per_year": 252,
        "include_interpretation": true
    }
    ```
    """
    try:
        result = metrics.calculate_performance_metrics(
            returns=request.returns,
            risk_free_rate=request.risk_free_rate,
            periods_per_year=request.periods_per_year,
            include_interpretation=request.include_interpretation
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@router.post("/sharpe")
async def calculate_sharpe_endpoint(request: SharpeRatioRequest):
    """
    Calculate Sharpe Ratio only.

    Sharpe Ratio measures risk-adjusted returns (excess return per unit of volatility).

    **Interpretation:**
    - > 2.0: Excellent
    - > 1.0: Good
    - > 0.5: Acceptable
    - < 0.5: Poor

    **Example:**
    ```json
    {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "risk_free_rate": 0.0,
        "periods_per_year": 252
    }
    ```
    """
    try:
        sharpe = metrics.calculate_sharpe_ratio(
            returns=request.returns,
            risk_free_rate=request.risk_free_rate,
            periods_per_year=request.periods_per_year
        )
        return {"sharpe_ratio": sharpe}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@router.post("/max-drawdown")
async def calculate_max_drawdown_endpoint(returns: List[float]):
    """
    Calculate Maximum Drawdown only.

    Maximum Drawdown shows the largest peak-to-trough decline.
    Always negative or zero.

    **Interpretation:**
    - Closer to 0: Better (less severe drawdown)
    - < -0.20: Significant risk
    - < -0.50: Very high risk

    **Example:**
    ```json
    [0.01, -0.02, 0.03, 0.02, -0.01]
    ```
    """
    try:
        mdd = metrics.calculate_max_drawdown(returns)
        return {"max_drawdown": mdd}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@router.post("/cagr")
async def calculate_cagr_endpoint(request: MetricRequest):
    """
    Calculate CAGR (Compound Annual Growth Rate) only.

    CAGR represents the annualized return rate.

    **Interpretation:**
    - Positive: Profitable
    - > 0.15: Strong performance
    - > 0.30: Exceptional performance

    **Example:**
    ```json
    {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "periods_per_year": 252
    }
    ```
    """
    try:
        cagr = metrics.calculate_cagr(request.returns, request.periods_per_year)
        return {"cagr": cagr}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@router.post("/calmar")
async def calculate_calmar_endpoint(request: MetricRequest):
    """
    Calculate Calmar Ratio only.

    Calmar Ratio measures return per unit of maximum drawdown.
    Higher is better.

    **Interpretation:**
    - > 3.0: Exceptional
    - > 1.0: Good
    - > 0.5: Decent
    - < 0.5: Poor

    **Example:**
    ```json
    {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "periods_per_year": 252
    }
    ```
    """
    try:
        calmar = metrics.calculate_calmar_ratio(request.returns, request.periods_per_year)
        return {"calmar_ratio": calmar}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@router.post("/win-rate")
async def calculate_win_rate_endpoint(returns: List[float]):
    """
    Calculate Win Rate only.

    Win Rate is the percentage of profitable periods.

    **Interpretation:**
    - > 0.60: High win rate
    - > 0.50: Moderate win rate
    - < 0.40: Low win rate

    **Note:** Low win rate can be excellent if winners are much larger than losers.

    **Example:**
    ```json
    [0.01, -0.02, 0.03, 0.02, -0.01]
    ```
    """
    try:
        win_rate = metrics.calculate_win_rate(returns)
        return {"win_rate": win_rate}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@router.post("/all")
async def calculate_all_metrics_endpoint(request: MetricRequest):
    """
    Calculate ALL individual metrics in a single call.

    This endpoint calls each metric function separately and returns all results.
    Unlike `/performance`, this endpoint provides individual metric values without
    interpretation or metadata - just the raw numbers.

    **Returns:**
    - sharpe_ratio: Risk-adjusted return metric
    - max_drawdown: Worst peak-to-trough decline
    - cagr: Compound annual growth rate
    - calmar_ratio: Return per unit of maximum drawdown
    - win_rate: Percentage of profitable periods

    **Example Request:**
    ```json
    {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "periods_per_year": 252
    }
    ```

    **Example Response:**
    ```json
    {
        "sharpe_ratio": 1.23,
        "max_drawdown": -0.04,
        "cagr": 0.078,
        "calmar_ratio": 1.95,
        "win_rate": 0.6
    }
    ```
    """
    try:
        # Calculate each metric individually
        sharpe = metrics.calculate_sharpe_ratio(
            request.returns,
            risk_free_rate=0.0,
            periods_per_year=request.periods_per_year
        )
        max_dd = metrics.calculate_max_drawdown(request.returns)
        cagr = metrics.calculate_cagr(request.returns, request.periods_per_year)
        calmar = metrics.calculate_calmar_ratio(request.returns, request.periods_per_year)
        win_rate = metrics.calculate_win_rate(request.returns)

        return {
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "cagr": cagr,
            "calmar_ratio": calmar,
            "win_rate": win_rate
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")
