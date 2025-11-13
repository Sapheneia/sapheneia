"""
Trading Strategies API Endpoints

Implements the REST API for trading strategy execution:
- POST /execute: Execute a trading strategy
- GET /strategies: List available strategies
- GET /status: Service status check
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, Body
import logging
from typing import Dict, Any

# Import schemas
from ..schemas.schema import (
    StrategyRequest,
    StrategyResponse,
    StrategyListResponse,
    StrategyInfo,
    StrategyTypeEnum,
)

# Import services
from ..services.trading import TradingStrategy

# Import core utilities
from ..core.security import get_api_key
from ..core.rate_limit import limiter, get_rate_limit
from ..core.exceptions import (
    TradingException,
    InvalidStrategyError,
    InsufficientCapitalError,
    InvalidParametersError,
    StrategyStoppedError,
)

logger = logging.getLogger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/trading",
    tags=["Trading Strategies"],
)

# Note: Exception handlers are registered in main.py at the app level
# Routers don't support exception_handler decorator


# ========== ENDPOINTS ==========


@router.post("/execute", response_model=StrategyResponse)
@limiter.limit(get_rate_limit("execute"))
async def execute_strategy(
    request: Request,
    response: Response,
    strategy_request: StrategyRequest = Body(...),
    api_key: str = Depends(get_api_key),
) -> StrategyResponse:
    """
    Execute a trading strategy and return the recommended action.

    This endpoint accepts strategy parameters, validates them, executes the
    trading strategy, and returns the execution result with updated state.

    **Supported Strategies:**
    - **threshold**: Price difference-based strategy with configurable thresholds
    - **return**: Expected return-based strategy with position sizing
    - **quantile**: Empirical quantile-based strategy using historical distribution

    **Request Body:**
    The request body varies by strategy type. See individual strategy schemas
    for required and optional parameters.

    **Common Parameters (all strategies):**
    - `strategy_type`: Strategy type ("threshold", "return", or "quantile")
    - `forecast_price`: Forecasted price (must be > 0)
    - `current_price`: Current market price (must be > 0)
    - `current_position`: Current position size (must be >= 0, long-only)
    - `available_cash`: Available cash (must be >= 0)
    - `initial_capital`: Initial capital (must be > 0)

    **Response:**
    - `action`: Trading action ("buy", "sell", or "hold")
    - `size`: Position size executed (shares/units)
    - `value`: Dollar value of trade
    - `reason`: Explanation of the action
    - `available_cash`: Cash remaining after trade
    - `position_after`: Position size after trade
    - `stopped`: Whether strategy is stopped (no capital remaining)

    **Status Codes:**
    - 200: Successful execution
    - 400: Invalid parameters or strategy error
    - 401: Invalid or missing API key
    - 429: Rate limit exceeded
    - 500: Internal server error

    **Example Request (Threshold Strategy):**
    ```json
    {
        "strategy_type": "threshold",
        "forecast_price": 105.0,
        "current_price": 100.0,
        "current_position": 0.0,
        "available_cash": 100000.0,
        "initial_capital": 100000.0,
        "threshold_type": "absolute",
        "threshold_value": 0.0,
        "execution_size": 100.0
    }
    ```

    **Example Response:**
    ```json
    {
        "action": "buy",
        "size": 100.0,
        "value": 10000.0,
        "reason": "Forecast 105.00 > Price 100.00, magnitude 5.0000 > threshold 0.0000",
        "available_cash": 90000.0,
        "position_after": 100.0,
        "stopped": false
    }
    ```
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(
        f"[{request_id}] 📥 Received execute request: strategy_type={strategy_request.strategy_type}"
    )

    try:
        # Convert Pydantic model to dict for TradingStrategy
        params = strategy_request.model_dump(exclude_none=True)

        # Convert strategy_type enum to string if needed
        if isinstance(params.get("strategy_type"), StrategyTypeEnum):
            params["strategy_type"] = params["strategy_type"].value

        # Execute trading strategy
        result = TradingStrategy.execute_trading_signal(params)

        # Convert result dict to StrategyResponse
        response_obj = StrategyResponse(**result)

        logger.info(
            f"[{request_id}] ✅ Strategy executed successfully: action={response_obj.action}, "
            f"size={response_obj.size:.2f}, value=${response_obj.value:.2f}"
        )

        return response_obj

    except (
        InvalidStrategyError,
        InsufficientCapitalError,
        InvalidParametersError,
        StrategyStoppedError,
    ) as e:
        # These are expected exceptions, already logged in TradingStrategy
        request_id = getattr(request.state, "request_id", "unknown")
        logger.warning(
            f"[{request_id}] Strategy execution failed: {e.error_code} - {e.message}"
        )
        raise HTTPException(status_code=e.suggested_status_code, detail=e.to_dict())

    except TradingException as e:
        # Other trading exceptions
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(f"[{request_id}] Trading exception: {e.error_code} - {e.message}")
        raise HTTPException(status_code=e.suggested_status_code, detail=e.to_dict())

    except Exception as e:
        # Unexpected exceptions
        logger.exception(
            f"Unexpected error during strategy execution: {type(e).__name__}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred during strategy execution",
                "details": {"error_type": type(e).__name__},
            },
        )


@router.get("/strategies", response_model=StrategyListResponse)
@limiter.limit(get_rate_limit("strategies"))
async def list_strategies(request: Request, response: Response) -> StrategyListResponse:
    """
    List all available trading strategies and their parameters.

    Returns information about all supported strategy types including
    required and optional parameters.

    **Response:**
    - `strategies`: List of strategy information objects

    **Status Codes:**
    - 200: Success
    - 429: Rate limit exceeded

    **Example Response:**
    ```json
    {
        "strategies": [
            {
                "type": "threshold",
                "description": "Threshold-based strategy with configurable threshold types",
                "parameters": {
                    "required": ["forecast_price", "current_price", "threshold_type", "threshold_value"],
                    "optional": ["execution_size", "which_history", "window_history"]
                }
            }
        ]
    }
    ```
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.debug(f"[{request_id}] Listing available strategies")

    strategies = [
        StrategyInfo(
            type="threshold",
            description="Threshold-based strategy with configurable threshold types (absolute, percentage, std_dev, ATR)",
            parameters={
                "required": [
                    "strategy_type",
                    "forecast_price",
                    "current_price",
                    "current_position",
                    "available_cash",
                    "initial_capital",
                    "threshold_type",
                    "threshold_value",
                ],
                "optional": [
                    "execution_size",
                    "which_history",
                    "window_history",
                    "min_history_length",
                    "open_history",
                    "high_history",
                    "low_history",
                    "close_history",
                ],
                "conditional": {
                    "atr": "All OHLC histories required",
                    "std_dev": "One of OHLC histories required",
                },
            },
        ),
        StrategyInfo(
            type="return",
            description="Return-based strategy with position sizing options (fixed, proportional, normalized)",
            parameters={
                "required": [
                    "strategy_type",
                    "forecast_price",
                    "current_price",
                    "current_position",
                    "available_cash",
                    "initial_capital",
                    "position_sizing",
                    "threshold_value",
                ],
                "optional": [
                    "execution_size",
                    "max_position_size",
                    "min_position_size",
                    "which_history",
                    "window_history",
                    "min_history_length",
                    "open_history",
                    "high_history",
                    "low_history",
                    "close_history",
                ],
                "conditional": {
                    "normalized": "History data required for normalized position sizing"
                },
            },
        ),
        StrategyInfo(
            type="quantile",
            description="Quantile-based strategy using empirical quantiles from historical distribution",
            parameters={
                "required": [
                    "strategy_type",
                    "forecast_price",
                    "current_price",
                    "current_position",
                    "available_cash",
                    "initial_capital",
                    "which_history",
                    "window_history",
                    "quantile_signals",
                    "open_history",
                    "high_history",
                    "low_history",
                    "close_history",
                ],
                "optional": [
                    "position_sizing",
                    "execution_size",
                    "max_position_size",
                    "min_position_size",
                    "min_history_length",
                ],
            },
        ),
    ]

    return StrategyListResponse(strategies=strategies)


@router.get("/status")
@limiter.limit(get_rate_limit("health"))
async def get_status(request: Request, response: Response) -> Dict[str, Any]:
    """
    Get trading strategies service status.

    Returns health check information for the trading strategies service.

    **Response:**
    - `status`: Service status ("healthy" or "unhealthy")
    - `service`: Service name
    - `version`: Service version
    - `available_strategies`: List of available strategy types

    **Status Codes:**
    - 200: Success
    - 429: Rate limit exceeded

    **Example Response:**
    ```json
    {
        "status": "healthy",
        "service": "trading-strategies",
        "version": "1.0.0",
        "available_strategies": ["threshold", "return", "quantile"]
    }
    ```
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.debug(f"[{request_id}] Status check requested")

    return {
        "status": "healthy",
        "service": "trading-strategies",
        "version": "1.0.0",
        "available_strategies": [e.value for e in StrategyTypeEnum],
    }
