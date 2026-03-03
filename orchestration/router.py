"""
Orchestration Router

FastAPI router exposing the unified orchestration API for Aleutian integration.

Endpoints:
    POST /orchestration/v1/predict      - Unified inference endpoint
    GET  /orchestration/v1/health       - Health check
    GET  /orchestration/v1/models       - List available models
    GET  /orchestration/v1/strategies   - List available strategies
    GET  /orchestration/v1/strategies/{name} - Get strategy by name
    POST /v1/timeseries/forecast        - Legacy endpoint (deprecated)

The new /orchestration/v1/predict endpoint is the recommended integration point.
The legacy /v1/timeseries/forecast is maintained for backwards compatibility.
"""

import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse
import yaml

from shared.errors import SapheneiaError, ValidationError, ComputationError

from .schema import (
    InferenceRequest,
    InferenceResponse,
    LegacyForecastRequest,
    LegacyForecastResponse,
    Period,
    DataSource,
)
from .service import InferenceService, LegacyCompatService

logger = logging.getLogger(__name__)

# Strategies directory (relative to repo root)
STRATEGIES_DIR = Path(__file__).parent.parent / "simulations" / "strategies"

# Create router
router = APIRouter(tags=["Orchestration"])


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_inference_service() -> InferenceService:
    """
    Dependency injection for InferenceService.

    In production, this could read from config or environment.
    """
    from forecast.core.config import settings
    return InferenceService(
        base_url=f"http://localhost:{settings.API_PORT}",
        api_key=settings.API_SECRET_KEY,
    )


def get_legacy_service(
    inference_service: InferenceService = Depends(get_inference_service)
) -> LegacyCompatService:
    """Dependency injection for legacy compat service."""
    return LegacyCompatService(inference_service)


async def verify_api_key(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> str:
    """
    Verify API key from Authorization header or X-API-Key header.

    Returns the validated key or raises HTTPException.
    """
    from forecast.core.config import settings

    # Extract key from either header
    key = None
    if authorization and authorization.startswith("Bearer "):
        key = authorization[7:]
    elif x_api_key:
        key = x_api_key

    if not key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide via 'Authorization: Bearer <key>' or 'X-API-Key' header."
        )

    if key != settings.API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return key


# =============================================================================
# ORCHESTRATION ENDPOINTS
# =============================================================================

@router.post(
    "/orchestration/v1/predict",
    response_model=InferenceResponse,
    summary="Run model inference",
    description="""
    Unified orchestration endpoint for all forecasting models.

    This is the primary integration point for Aleutian orchestrator.

    **Request Contract:**
    - `request_id`: Unique UUID for tracing
    - `ticker`: Symbol (e.g., "SPY", "BTCUSDT")
    - `model`: Model identifier (e.g., "amazon/chronos-t5-tiny")
    - `context`: Historical data with full metadata (values, period, source, dates)
    - `horizon`: Forecast specification (length, period)

    **Response Contract:**
    - `request_id`: Links to originating request
    - `response_id`: Unique response identifier
    - `forecast`: Predicted values with dates
    - `context_summary`: Echo of context used
    - `metadata`: Inference timing and device info
    """,
)
async def predict(
    request: InferenceRequest,
    service: InferenceService = Depends(get_inference_service),
    api_key: str = Depends(verify_api_key),
) -> InferenceResponse:
    """
    Run model inference on provided context data.

    Args:
        request: Unified inference request

    Returns:
        Unified inference response with forecast
    """
    try:
        return await service.predict(request)
    except SapheneiaError:
        raise  # Already structured, let handler deal with it
    except ValueError as e:
        logger.error(f"Inference error: {e}")
        raise ValidationError(
            message=str(e),
            details={"model": request.model, "ticker": request.ticker},
        )
    except Exception as e:
        logger.exception(f"Inference failed: {e}")
        raise ComputationError(
            message=f"Inference failed: {str(e)}",
            details={"model": request.model, "ticker": request.ticker},
        )


@router.get(
    "/orchestration/v1/health",
    summary="Health check",
    description="Check if orchestration service is running.",
)
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "orchestration"}


@router.get(
    "/orchestration/v1/models",
    summary="List available models",
    description="Get list of available model families and their status.",
)
async def list_models():
    """List available models and their families."""
    return {
        "models": [
            {
                "family": "chronos",
                "variants": [
                    "amazon/chronos-t5-tiny",
                    "amazon/chronos-t5-mini",
                    "amazon/chronos-t5-small",
                    "amazon/chronos-t5-base",
                    "amazon/chronos-t5-large",
                    "amazon/chronos-bolt-mini",
                    "amazon/chronos-bolt-small",
                    "amazon/chronos-bolt-base",
                ],
                "status": "available",
            },
            {
                "family": "timesfm",
                "variants": [
                    "google/timesfm-1.0-200m",
                    "google/timesfm-2.0-500m-pytorch",
                ],
                "status": "available",
            },
            {
                "family": "moirai",
                "variants": [
                    "salesforce/moirai-1.1-R-small",
                    "salesforce/moirai-1.1-R-base",
                    "salesforce/moirai-1.1-R-large",
                ],
                "status": "available",
            },
            {
                "family": "tirex",
                "variants": [
                    "NX-AI/TiRex",
                ],
                "status": "available",
            },
        ]
    }


# =============================================================================
# STRATEGY ENDPOINTS
# =============================================================================

@router.get(
    "/orchestration/v1/strategies",
    summary="List available strategies",
    description="""
    List all available backtest strategy configurations.

    Returns a list of strategy names that can be loaded via the
    `/orchestration/v1/strategies/{name}` endpoint.
    """,
)
async def list_strategies() -> Dict[str, List[str]]:
    """
    List all available strategy YAML files.

    Returns:
        Dictionary with "strategies" key containing list of strategy names.
    """
    if not STRATEGIES_DIR.exists():
        logger.warning(f"Strategies directory not found: {STRATEGIES_DIR}")
        return {"strategies": []}

    strategies = [f.stem for f in STRATEGIES_DIR.glob("*.yaml") if f.is_file()]
    strategies.sort()

    logger.info(f"Found {len(strategies)} strategies")
    return {"strategies": strategies}


@router.get(
    "/orchestration/v1/strategies/{name}",
    summary="Get strategy configuration",
    description="""
    Get a specific backtest strategy configuration by name.

    The returned JSON can be used directly with Aleutian's evaluation CLI:

    ```bash
    aleutian eval --config http://localhost:12210/orchestration/v1/strategies/spy_threshold_v1
    ```

    **Response Schema:**
    - `metadata`: Strategy identity (id, version, description, author, created)
    - `evaluation`: Ticker and date range configuration
    - `forecast`: Model and forecasting parameters
    - `trading`: Portfolio and strategy parameters
    """,
)
async def get_strategy(name: str) -> Dict[str, Any]:
    """
    Get a strategy configuration by name.

    Args:
        name: Strategy name (filename without .yaml extension)

    Returns:
        Parsed strategy configuration as JSON.

    Raises:
        HTTPException 404: If strategy not found.
    """
    # Validate strategy name to prevent path traversal
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise ValidationError(
            message=f"Invalid strategy name: '{name}'. Must contain only alphanumeric characters, hyphens, and underscores.",
            details={"name": name},
        )

    strategy_path = STRATEGIES_DIR / f"{name}.yaml"

    if not strategy_path.exists():
        logger.warning(f"Strategy not found: {name}")
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{name}' not found. Use /orchestration/v1/strategies to list available strategies."
        )

    try:
        with open(strategy_path, "r") as f:
            strategy = yaml.safe_load(f)

        logger.info(f"Loaded strategy: {name}")
        return strategy

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse strategy YAML: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse strategy '{name}': {str(e)}"
        )


# =============================================================================
# LEGACY ENDPOINT (Deprecated)
# =============================================================================

@router.post(
    "/v1/timeseries/forecast",
    response_model=LegacyForecastResponse,
    summary="[DEPRECATED] Legacy forecast endpoint",
    description="""
    **DEPRECATED**: Use `/orchestration/v1/predict` instead.

    This endpoint maintains backwards compatibility with existing Aleutian
    integrations. It will be removed in a future version.

    The legacy contract:
    - Request: name, context_period_size, forecast_period_size, model, recent_data
    - Response: name, forecast, message
    """,
    deprecated=True,
)
async def legacy_forecast(
    request: Request,
    service: LegacyCompatService = Depends(get_legacy_service),
) -> LegacyForecastResponse:
    """
    Legacy forecast endpoint for backwards compatibility.

    Converts legacy request to new format, runs inference, converts back.
    """
    try:
        # Parse raw body to handle both legacy field names
        body = await request.json()

        # Build legacy request from body
        legacy_request = LegacyForecastRequest(
            name=body.get("name", body.get("ticker", "")),
            context_period_size=body.get("context_period_size", len(body.get("recent_data", []))),
            forecast_period_size=body.get("forecast_period_size", body.get("horizon", 10)),
            model=body.get("model", ""),
            recent_data=body.get("recent_data", body.get("data", [])),
            as_of_date=body.get("as_of_date"),
        )

        # Determine source from header or default
        source = DataSource.INFLUXDB

        return await service.forecast(legacy_request, source=source)

    except SapheneiaError:
        raise
    except ValueError as e:
        logger.error(f"Legacy forecast error: {e}")
        raise ValidationError(message=str(e))
    except Exception as e:
        logger.exception(f"Legacy forecast failed: {e}")
        raise ComputationError(message=f"Forecast failed: {str(e)}")
