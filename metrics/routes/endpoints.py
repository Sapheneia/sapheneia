"""
Metrics API Endpoints

REST API endpoints for financial performance metrics calculation.
Consolidated single endpoint design for uniform interface.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from metrics.core import metrics

router = APIRouter(prefix="/compute", tags=["Metrics Computation"])


# --- Request/Response Schemas ---

class ComputeRequest(BaseModel):
    """Unified request model for metrics computation."""
    returns: List[float] = Field(..., description="Return series (e.g., daily returns)")
    metric: Literal["performance", "all", "sharpe", "max_drawdown", "cagr", "calmar", "win_rate"] = Field(
        default="performance",
        description="Metric to compute: 'performance' (all with interpretation), 'all' (all clean), or individual metrics"
    )
    risk_free_rate: float = Field(
        default=0.0,
        description="Annual risk-free rate (e.g., 0.04 for 4%) - used for Sharpe ratio"
    )
    periods_per_year: int = Field(
        default=252,
        description="Trading periods per year (252=daily, 52=weekly, 12=monthly)"
    )
    include_interpretation: bool = Field(
        default=True,
        description="Include human-readable interpretation (only for 'performance' metric)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
                    "metric": "performance",
                    "risk_free_rate": 0.0,
                    "periods_per_year": 252,
                    "include_interpretation": True
                },
                {
                    "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
                    "metric": "all",
                    "periods_per_year": 252
                },
                {
                    "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
                    "metric": "sharpe",
                    "risk_free_rate": 0.04,
                    "periods_per_year": 252
                }
            ]
        }
    }


# --- Unified Compute Endpoint ---

@router.post("/", response_model_exclude_none=True)
async def compute_metrics(request: ComputeRequest) -> Dict[str, Any]:
    """
    **Unified Metrics Computation Endpoint**

    Calculate financial performance metrics for a return series.
    Use the `metric` parameter to specify which metric(s) to compute.

    ## Metric Options:

    - **performance**: All 5 metrics with interpretation & metadata (default)
    - **all**: All 5 metrics, clean response (no interpretation/metadata)
    - **sharpe**: Sharpe Ratio only
    - **max_drawdown**: Maximum Drawdown only
    - **cagr**: CAGR only
    - **calmar**: Calmar Ratio only
    - **win_rate**: Win Rate only

    ## Example Requests:

    **Get all metrics with interpretation:**
    ```json
    {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "performance",
        "risk_free_rate": 0.0,
        "periods_per_year": 252,
        "include_interpretation": true
    }
    ```

    **Get all metrics (clean):**
    ```json
    {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "all"
    }
    ```

    **Get single metric:**
    ```json
    {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "sharpe",
        "risk_free_rate": 0.04
    }
    ```

    ## Returns:

    Response format varies by `metric` parameter:

    - **performance**: `{sharpe_ratio, max_drawdown, cagr, calmar_ratio, win_rate, interpretation?, metadata}`
    - **all**: `{sharpe_ratio, max_drawdown, cagr, calmar_ratio, win_rate}`
    - **sharpe**: `{sharpe_ratio}`
    - **max_drawdown**: `{max_drawdown}`
    - **cagr**: `{cagr}`
    - **calmar**: `{calmar_ratio}`
    - **win_rate**: `{win_rate}`
    """
    try:
        # Route to appropriate metric calculation
        if request.metric == "performance":
            # All metrics with interpretation & metadata
            result = metrics.calculate_performance_metrics(
                returns=request.returns,
                risk_free_rate=request.risk_free_rate,
                periods_per_year=request.periods_per_year,
                include_interpretation=request.include_interpretation
            )
            return result

        elif request.metric == "all":
            # All metrics, clean response (no interpretation/metadata)
            sharpe = metrics.calculate_sharpe_ratio(
                request.returns,
                risk_free_rate=request.risk_free_rate,
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

        elif request.metric == "sharpe":
            sharpe = metrics.calculate_sharpe_ratio(
                request.returns,
                risk_free_rate=request.risk_free_rate,
                periods_per_year=request.periods_per_year
            )
            return {"sharpe_ratio": sharpe}

        elif request.metric == "max_drawdown":
            max_dd = metrics.calculate_max_drawdown(request.returns)
            return {"max_drawdown": max_dd}

        elif request.metric == "cagr":
            cagr = metrics.calculate_cagr(request.returns, request.periods_per_year)
            return {"cagr": cagr}

        elif request.metric == "calmar":
            calmar = metrics.calculate_calmar_ratio(request.returns, request.periods_per_year)
            return {"calmar_ratio": calmar}

        elif request.metric == "win_rate":
            win_rate = metrics.calculate_win_rate(request.returns)
            return {"win_rate": win_rate}

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric: {request.metric}. Must be one of: performance, all, sharpe, max_drawdown, cagr, calmar, win_rate"
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")
