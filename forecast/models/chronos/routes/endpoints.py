"""
Chronos API Endpoints

REST API for Chronos model operations.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, Body
import logging
import time
from typing import Optional, Dict, Any

# Import schemas
from ..schemas.schema import (
    ModelInitInput, ModelInitOutput,
    InferenceInput, InferenceOutput,
    ShutdownOutput, StatusOutput
)

# Import services
from ..services import model as chronos_model_service

# Import core utilities
from ....core.security import get_api_key
from ....core.rate_limit import limiter, get_rate_limit
from ....core.exceptions import (
    SapheneiaException,
    ModelNotInitializedError,
    ModelInitializationError,
)

logger = logging.getLogger(__name__)

# Create router with prefix and dependencies
router = APIRouter(
    prefix="/chronos",
    tags=["Chronos"],
    dependencies=[Depends(get_api_key)]
)


@router.post("/initialization", response_model=ModelInitOutput)
@limiter.limit(get_rate_limit("initialization"))
async def initialize_model_endpoint(
    request: Request,
    response: Response,
    init_input: ModelInitInput = Body()
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
            model_info=chronos_model_service.get_model_info()
        )

    if status == "initializing":
        logger.warning("Initialization already in progress")
        raise HTTPException(
            status_code=409,
            detail="Model initialization already in progress"
        )

    try:
        chronos_model_service.initialize_model(
            model_variant=init_input.model_variant,
            device=init_input.device
        )

        model_info = chronos_model_service.get_model_info()

        logger.info(f"✅ Initialization successful: {model_info}")

        return ModelInitOutput(
            message=f"Model initialized successfully",
            model_status="ready",
            model_info=model_info
        )

    except (ModelInitializationError, chronos_model_service.ModelInitializationError) as e:
        logger.error(f"❌ Initialization error: {e}")
        raise ModelInitializationError(str(e))

    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        from ....core.exceptions import ConfigurationError
        raise ConfigurationError(str(e), setting="model_variant")

    except Exception as e:
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

    return StatusOutput(
        model_status=status,
        details=details
    )


@router.post("/inference", response_model=InferenceOutput)
@limiter.limit(get_rate_limit("inference"))
async def inference_endpoint(
    request: Request,
    response: Response,
    input_data: InferenceInput = Body()
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
    logger.info(f"📥 Received inference request")
    logger.info(f"   Context length: {len(input_data.context)}")
    logger.info(f"   Prediction length: {input_data.prediction_length}")
    logger.info("=" * 80)

    # Check model status
    status, error_msg = chronos_model_service.get_status()
    if status != "ready":
        logger.error(f"❌ Inference called but model not ready. Status: {status}")
        raise HTTPException(
            status_code=409,
            detail=f"Model not initialized. Status: {status}. "
                   f"Please call /initialization first."
        )

    start_time = time.time()

    try:
        results = chronos_model_service.run_inference(
            context=input_data.context,
            prediction_length=input_data.prediction_length,
            num_samples=input_data.num_samples,
            temperature=input_data.temperature,
            top_k=input_data.top_k,
            top_p=input_data.top_p
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
                "api_version": "1.0.0"
            }
        )

    except (ModelNotInitializedError, chronos_model_service.ModelNotInitializedError) as e:
        logger.error(f"❌ Model not initialized: {e}")
        raise ModelNotInitializedError(str(e))

    except SapheneiaException:
        raise

    except Exception as e:
        logger.exception(f"❌ Inference failed")
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
