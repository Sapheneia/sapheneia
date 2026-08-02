"""
Chronos API Endpoints

REST API for Chronos model operations.
"""

import logging
import os
import time

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from shared.contracts import ForecastEnvelope, ForecastRequest, QuantileBand
from shared.model_family import ModelFamily

from ....core.exceptions import (
    ModelInitializationError,
    ModelNotInitializedError,
    SapheneiaException,
)
from ....core.rate_limit import get_rate_limit, limiter

# Import core utilities
from ....core.security import get_api_key

# Import schemas
from ..schemas.schema import (
    InferenceInput,
    InferenceOutput,
    ModelInitInput,
    ModelInitOutput,
    ShutdownOutput,
    StatusOutput,
)

# Import services
from ..services import model as chronos_model_service

logger = logging.getLogger(__name__)

# Create router with prefix and dependencies
router = APIRouter(prefix="/chronos", tags=["Chronos"], dependencies=[Depends(get_api_key)])


@router.post("/initialization", response_model=ModelInitOutput)
@limiter.limit(get_rate_limit("initialization"))
async def initialize_model_endpoint(
    request: Request, response: Response, init_input: ModelInitInput = Body()
):
    """
    Initialize the Chronos model.

    The model will be loaded from the HuggingFace cache (HF_HOME).
    If MODEL_VARIANT environment variable is set, it will be used as default.

    **Request Body:**
    - `model_variant`: Model identifier (e.g., 'amazon/chronos-t5-tiny')
    - `device`: Device to load on ('cpu', 'cuda', 'mps')

    **Returns:**
    - Initialization status and model information
    """
    logger.info(f"📥 Received initialization request: {init_input.model_dump(exclude_unset=True)}")

    # Check current status
    status, _ = chronos_model_service.get_status()

    if status == "ready":
        logger.warning("Model already initialized")
        return ModelInitOutput(
            message="Model already initialized",
            model_status="ready",
            model_info=chronos_model_service.get_model_info(),
        )

    if status == "initializing":
        logger.warning("Initialization already in progress")
        raise HTTPException(status_code=409, detail="Model initialization already in progress")

    try:
        chronos_model_service.initialize_model(
            model_variant=init_input.model_variant, device=init_input.device
        )

        model_info = chronos_model_service.get_model_info()

        logger.info(f"✅ Initialization successful: {model_info}")

        return ModelInitOutput(
            message="Model initialized successfully",
            model_status="ready",
            model_info=model_info,
        )

    except (
        ModelInitializationError,
        chronos_model_service.ModelInitializationError,
    ) as e:
        logger.error(f"❌ Initialization error: {e}")
        raise ModelInitializationError(str(e)) from e

    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        from ....core.exceptions import ConfigurationError

        raise ConfigurationError(str(e), setting="model_variant") from e

    except Exception:
        logger.exception("❌ Unexpected error during initialization")
        raise


@router.get("/status", response_model=StatusOutput)
@limiter.limit(get_rate_limit("default"))
async def get_model_status(request: Request, response: Response):
    """
    Check the current status of the Chronos model.

    **Returns:**
    - `model_status`: Current status ('uninitialized', 'initializing', 'ready', 'error')
    - `details`: Additional information about the model state
    """
    logger.debug("📊 Status endpoint called")

    status, error_msg = chronos_model_service.get_status()
    model_info = chronos_model_service.get_model_info()

    details = f"Model: {model_info.get('model_variant')}" if model_info else None
    if error_msg:
        details = f"{details}. Error: {error_msg}" if details else f"Error: {error_msg}"

    return StatusOutput(model_status=status, details=details)


@router.post("/inference", response_model=InferenceOutput)
@limiter.limit(get_rate_limit("inference"))
async def inference_endpoint(
    request: Request, response: Response, input_data: InferenceInput = Body()
):
    """
    Run Chronos inference on provided context.

    **Request Body:**
    - `context`: Historical time series values
    - `prediction_length`: Number of steps to forecast
    - `num_samples`: Number of sample trajectories (default: 20)
    - `temperature`: Sampling temperature (default: 1.0)
    - `top_k`: Top-k sampling parameter (default: 50)
    - `top_p`: Top-p sampling parameter (default: 1.0)

    **Returns:**
    - Forecast predictions (median, mean, quantiles, samples)
    - Execution metadata
    """
    logger.info("=" * 80)
    logger.info("📥 Received inference request")
    logger.info(f"   Context length: {len(input_data.context)}")
    logger.info(f"   Prediction length: {input_data.prediction_length}")
    logger.info("=" * 80)

    # Check model status
    status, error_msg = chronos_model_service.get_status()
    if status != "ready":
        if status == "uninitialized":
            try:
                body = await request.json()
            except Exception:
                body = {}
            model_variant = body.get("model_variant") or os.getenv("MODEL_VARIANT")
            if not model_variant:
                raise HTTPException(
                    status_code=400,
                    detail="model_variant not provided in request body and MODEL_VARIANT env var not set",
                )
            device = os.getenv("DEVICE", "cpu")
            logger.info(f"Lazy initializing Chronos model variant: {model_variant} on {device}")
            try:
                chronos_model_service.initialize_model(model_variant=model_variant, device=device)
            except Exception as e:
                logger.error(f"Failed to lazy initialize Chronos model: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to lazy initialize Chronos model: {e}",
                ) from e
        else:
            logger.error(f"❌ Inference called but model not ready. Status: {status}")
            raise HTTPException(
                status_code=409,
                detail=f"Model not initialized. Status: {status}. Please call /initialization first.",
            )

    start_time = time.time()

    try:
        results = chronos_model_service.run_inference(
            context=input_data.context,
            prediction_length=input_data.prediction_length,
            num_samples=input_data.num_samples,
            temperature=input_data.temperature,
            top_k=input_data.top_k,
            top_p=input_data.top_p,
        )

        total_time = time.time() - start_time

        logger.info("=" * 80)
        logger.info("✅ Inference request completed successfully")
        logger.info(f"   Total time: {total_time:.2f}s")
        logger.info("=" * 80)

        return InferenceOutput(
            prediction=results,
            execution_metadata={
                "total_time_seconds": round(total_time, 3),
                "model_version": chronos_model_service._model_variant,
                "api_version": "1.0.0",
            },
        )

    except (
        ModelNotInitializedError,
        chronos_model_service.ModelNotInitializedError,
    ) as e:
        logger.error(f"❌ Model not initialized: {e}")
        raise ModelNotInitializedError(str(e)) from e

    except SapheneiaException:
        raise

    except Exception:
        logger.exception("❌ Inference failed")
        raise


@router.post("/shutdown", response_model=ShutdownOutput)
@limiter.limit(get_rate_limit("default"))
async def shutdown_model_endpoint(request: Request, response: Response):
    """
    Shutdown the Chronos model and free resources.

    **Returns:**
    - Shutdown confirmation message
    """
    logger.info("🔄 Received shutdown request")

    success = chronos_model_service.shutdown_model()

    if success:
        logger.info("✅ Model shut down successfully")
        return ShutdownOutput(message="Model shut down successfully")
    else:
        logger.warning("⚠️  Model was not initialized")
        return ShutdownOutput(message="Model was not initialized or already shut down")


# --- Canonical forecast contract -------------------------------------------
#
# ``/inference`` above is the legacy, family-specific endpoint: it nests its
# result under ``prediction`` and consults ``model_variant`` from the request
# body only while the pipeline is uninitialized. The orchestrator speaks the
# canonical contract in ``shared.contracts`` instead, so that:
#
#   * one response shape covers every family (no shape-sniffing downstream), and
#   * a request that reaches the wrong container is REJECTED rather than being
#     served by whichever model this process loaded first.
#
# Which model this container serves is fixed by its MODEL_VARIANT env var. The
# request body never selects a model; it only asserts which one it expects.


def _container_model_id() -> str | None:
    """The model this container is pinned to serve."""
    loaded = chronos_model_service._model_variant
    return loaded or os.getenv("MODEL_VARIANT")


@router.post("/forecast", response_model=ForecastEnvelope)
@limiter.limit(get_rate_limit("default"))
async def forecast_endpoint(
    request: Request, response: Response, payload: ForecastRequest = Body()
):
    """
    Run a forecast using the canonical cross-family contract.

    **Request Body:** `context`, `prediction_length`, `num_samples`, `model_id`

    **Returns:** a `ForecastEnvelope` — top-level `median` plus `quantiles`.
    """
    served = _container_model_id()
    if served is None:
        raise HTTPException(
            status_code=503,
            detail="This container has no MODEL_VARIANT configured and no model loaded.",
        )
    if payload.model_id and payload.model_id != served:
        # The caller routed to the wrong container. Failing here is the whole
        # point: silently serving `served` would record a forecast under the
        # requested model_id that the requested model never produced.
        raise HTTPException(
            status_code=409,
            detail=(
                f"Model mismatch: this container serves {served!r} but the request "
                f"asked for {payload.model_id!r}. Route to that model's container."
            ),
        )

    status, _ = chronos_model_service.get_status()
    if status == "uninitialized":
        device = os.getenv("DEVICE", "cpu")
        logger.info("Lazy initializing Chronos %s on %s", served, device)
        chronos_model_service.initialize_model(model_variant=served, device=device)
        status, _ = chronos_model_service.get_status()
    if status != "ready":
        raise HTTPException(status_code=503, detail=f"Model not ready (status: {status})")

    start = time.time()
    results = chronos_model_service.run_inference(
        context=payload.context,
        prediction_length=payload.prediction_length,
        num_samples=payload.num_samples,
    )
    elapsed = time.time() - start

    quantiles = [
        QuantileBand(quantile=int(k) / 100.0, values=[float(v) for v in vals])
        for k, vals in (results.get("quantiles") or {}).items()
    ]
    return ForecastEnvelope(
        model_id=served,
        family=ModelFamily.CHRONOS.value,
        median=[float(v) for v in results["median"]],
        quantiles=sorted(quantiles, key=lambda b: b.quantile),
        metadata={
            "inference_time_seconds": round(elapsed, 3),
            "context_length": len(payload.context),
            "prediction_length": payload.prediction_length,
            "num_samples": payload.num_samples,
        },
    )
