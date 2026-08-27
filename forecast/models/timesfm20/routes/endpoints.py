"""
TimesFM-2.0 API Endpoints

Implements the REST API for TimesFM-2.0 model operations:
- /initialization: Initialize model
- /status: Check model status
- /inference: Run forecasting
- /shutdown: Unload model
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from shared.contracts import ForecastEnvelope, ForecastRequest, QuantileBand
from shared.model_family import ModelFamily

from ....core.config import settings
from ....core.data import DataFetchError
from ....core.exceptions import (
    DataError,
    DataValidationError,
    ModelInitializationError,
    ModelNotInitializedError,
    SapheneiaException,
)
from ....core.exceptions import DataFetchError as CoreDataFetchError
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
from ..services import data as timesfm_data_service
from ..services import model as timesfm_model_service

logger = logging.getLogger(__name__)

# Create router with prefix and dependencies
router = APIRouter(
    prefix="/timesfm20",
    tags=["TimesFM-2.0"],
    dependencies=[Depends(get_api_key)],  # Apply API key check to all routes
)

# ThreadPoolExecutor for CPU-bound operations (Phase 8: Performance Optimization)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="inference-worker")
logger.info(f"ThreadPoolExecutor initialized with {_executor._max_workers} workers")


# --- Initialization Endpoint ---


@router.post("/initialization", response_model=ModelInitOutput)
@limiter.limit(get_rate_limit("initialization"))
async def initialize_model_endpoint(
    request: Request, response: Response, init_input: ModelInitInput = Body()
):
    """
    Initialize the TimesFM-2.0 model from specified source.

    This endpoint loads the model weights into memory. It's a blocking call
    that must complete before inference can be performed.

    **Supported Sources:**
    - HuggingFace: Provide `checkpoint` parameter
    - Local: Provide `local_model_path` parameter

    **Request Body:**
    - `backend`: Computing backend ('cpu', 'gpu', 'tpu')
    - `context_len`: Context window length (32-2048)
    - `horizon_len`: Forecast horizon length (1-128)
    - `checkpoint`: HuggingFace repo ID (optional)
    - `local_model_path`: Local model file path (optional)

    **Returns:**
    - Initialization status and model information

    **Errors:**
    - 409: Model already initializing
    - 400: Invalid parameters
    - 500: Initialization failed
    """
    logger.info(f"📥 Received initialization request: {init_input.model_dump(exclude_unset=True)}")

    # Check current status
    status, _ = timesfm_model_service.get_status()

    if status == "ready":
        logger.warning("Initialization requested, but model already ready")
        return ModelInitOutput(
            message=f"Model already initialized ({timesfm_model_service.get_model_source_info()})",
            model_status="ready",
            model_info=timesfm_model_service.get_model_config(),
        )

    if status == "initializing":
        logger.warning("Initialization requested, but already in progress")
        raise HTTPException(status_code=409, detail="Model initialization already in progress")

    # Determine source type
    source_type = "hf"  # Default to HuggingFace
    if init_input.local_model_path:
        source_type = "local"
    elif not init_input.checkpoint and not init_input.local_model_path:
        # Use default checkpoint
        init_input.checkpoint = settings.TIMESFM20_DEFAULT_CHECKPOINT

    logger.info(f"🚀 Attempting initialization from source: {source_type}")

    try:
        # Call the blocking initialization function
        timesfm_model_service.initialize_model(
            source_type=source_type,
            backend=init_input.backend,
            context_len=init_input.context_len,
            horizon_len=init_input.horizon_len,
            checkpoint=init_input.checkpoint,
            local_model_path=init_input.local_model_path,
        )

        model_info = timesfm_model_service.get_model_config()
        source_info = timesfm_model_service.get_model_source_info()

        logger.info(f"✅ Initialization successful: {source_info}")

        return ModelInitOutput(
            message=f"Model initialized successfully from {source_info}",
            model_status="ready",
            model_info=model_info,
        )

    except (
        ModelInitializationError,
        timesfm_model_service.ModelInitializationError,
    ) as e:
        logger.error(f"❌ Initialization error: {e}")
        # Let SapheneiaException handler handle this
        if not isinstance(e, ModelInitializationError):
            raise ModelInitializationError(str(e), source=source_type) from e
        raise

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"❌ Configuration error: {e}")
        # Wrap in ConfigurationError
        from ....core.exceptions import ConfigurationError

        raise ConfigurationError(str(e), setting="model_checkpoint") from e

    except SapheneiaException:
        # Already structured - pass through
        raise

    except Exception as e:
        logger.exception("❌ Unexpected error during initialization")
        # Ensure status reflects failure
        if timesfm_model_service.get_status()[0] != "error":
            timesfm_model_service._model_status = "error"
            timesfm_model_service._error_message = f"Unexpected: {str(e)}"
        # Generic errors will be caught by generic_exception_handler
        raise


# --- Status Endpoint ---


@router.get("/status", response_model=StatusOutput)
@limiter.limit(get_rate_limit("default"))
async def get_model_status(request: Request, response: Response):
    """
    Check the current status of the TimesFM-2.0 model.

    **Returns:**
    - `model_status`: Current status ('uninitialized', 'initializing', 'ready', 'error')
    - `details`: Additional information about the model state

    **Status Values:**
    - `uninitialized`: Model has not been initialized
    - `initializing`: Model is currently being loaded
    - `ready`: Model is ready for inference
    - `error`: Model encountered an error during initialization
    """
    logger.debug("📊 Status endpoint called")

    status, error_msg = timesfm_model_service.get_status()
    source_info = timesfm_model_service.get_model_source_info()

    details = f"Source: {source_info}" if source_info else None
    if error_msg:
        details = f"{details}. Error: {error_msg}" if details else f"Error: {error_msg}"

    logger.debug(f"Status: {status}, Details: {details}")

    return StatusOutput(model_status=status, details=details)


# --- Inference Helper Function (Phase 8: Performance Optimization) ---


def _run_inference_sync(
    data_source: str, data_definition: dict[str, str], parameters: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """
    Synchronous inference function for thread pool execution.

    This function contains all the CPU-bound inference logic that will be
    executed in a separate thread to avoid blocking the async event loop.

    Args:
        data_source: Path or URL to data source
        data_definition: Column type definitions
        parameters: Model parameters (context_len, horizon_len, etc.)

    Returns:
        Tuple of (results_dict, visualization_data_dict)

    Raises:
        ModelNotInitializedError: If model is not initialized
        DataError: If data fetching/validation fails
        Exception: For unexpected errors
    """
    # Extract parameters with defaults
    context_len = parameters.get("context_len", settings.TIMESFM20_DEFAULT_CONTEXT_LEN)
    horizon_len = parameters.get("horizon_len", settings.TIMESFM20_DEFAULT_HORIZON_LEN)
    use_covariates = parameters.get("use_covariates", False)

    # --- Step 1: Load and Transform Data ---
    logger.info("📂 Loading and transforming data...")
    load_start = time.time()

    target_inputs, covariates, processed_data = (
        timesfm_data_service.load_and_transform_timesfm_data(
            data_source=data_source,
            data_definition=data_definition,
            parameters=parameters,
        )
    )

    load_time = time.time() - load_start
    logger.info(f"✅ Data loaded in {load_time:.2f}s")

    # --- Step 2: Validate Data ---
    logger.info("🔍 Validating data structure...")
    timesfm_data_service.validate_timesfm_data_structure(
        target_inputs=target_inputs,
        covariates=covariates,
        context_len=context_len,
        horizon_len=horizon_len,
    )

    # --- Step 3: Format Inputs ---
    # Ensure target_inputs is in batch format (list of lists)
    if isinstance(target_inputs[0], (int, float)):
        target_inputs_formatted = [target_inputs]
    else:
        target_inputs_formatted = target_inputs

    # --- Step 4: Run Inference ---
    logger.info("🔮 Running inference...")
    inference_start = time.time()

    results = timesfm_model_service.run_inference(
        target_inputs=target_inputs_formatted,
        covariates=covariates if use_covariates and any(covariates.values()) else None,
        parameters=parameters,
    )

    inference_time = time.time() - inference_start
    logger.info(f"✅ Inference completed in {inference_time:.2f}s")

    # --- Step 5: Prepare Visualization Data ---
    logger.info("📊 Preparing visualization data...")

    # Find target column
    target_column = None
    for col, dtype in data_definition.items():
        if dtype == "target":
            target_column = col
            break

    visualization_data = timesfm_data_service.prepare_timesfm_visualization_data(
        processed_data=processed_data,
        target_inputs=target_inputs,
        target_column=target_column,
        context_len=context_len,
        horizon_len=horizon_len,
    )

    # --- Step 6: Convert Results to JSON-Serializable Format ---
    # Convert numpy arrays to lists
    for key, value in results.items():
        if isinstance(value, np.ndarray):
            if value.ndim > 1:
                results[key] = value.tolist()
            else:
                results[key] = value.tolist()

    return results, visualization_data


# --- Inference Endpoint ---


@router.post("/inference", response_model=InferenceOutput)
@limiter.limit(get_rate_limit("inference"))
async def inference_endpoint(
    request: Request,
    response: Response,
    input_data: InferenceInput = Body(),
    track: bool = Query(False, description="Enable MLflow tracking (not yet implemented)"),
):
    """
    Run TimesFM-2.0 inference on provided data.

    This endpoint fetches data from the specified source, processes it according
    to the data definition, and runs the TimesFM model to generate forecasts.

    **Request Body:**
    - `data_source_url_or_path`: URL or path to data file
    - `data_definition`: Column type definitions (must include one 'target')
    - `parameters`: Inference parameters

    **Parameters:**
    - `context_len`: Context window length (default: 64)
    - `horizon_len`: Forecast horizon length (default: 24)
    - `use_covariates`: Enable covariates-enhanced forecasting
    - `use_quantiles`: Enable quantile forecasting
    - `quantile_indices`: Quantile indices to use (default: [1,3,5,7,9])
    - `context_start_date`: Start date for context window (optional)
    - `context_end_date`: End date for context window (optional)

    **Returns:**
    - Forecast predictions (point and quantile)
    - Metadata about the forecast
    - Visualization data

    **Errors:**
    - 409: Model not initialized
    - 400: Invalid data or parameters
    - 500: Inference failed
    """
    logger.info("=" * 80)
    logger.info("📥 Received inference request")
    logger.info(f"   Data source: {input_data.data_source_url_or_path}")
    logger.info(f"   Parameters: {input_data.parameters}")
    logger.info("=" * 80)

    # Check model status
    status, error_msg = timesfm_model_service.get_status()
    if status != "ready":
        logger.error(f"❌ Inference called but model not ready. Status: {status}")
        raise HTTPException(
            status_code=409,
            detail=f"Model not initialized. Status: {status}. Please call /initialization first.",
        )

    start_time = time.time()

    try:
        # Extract parameters with defaults
        parameters = input_data.parameters
        load_start = time.time()

        # --- Phase 8: Run inference asynchronously in thread pool ---
        # This prevents blocking the async event loop during CPU-bound operations
        logger.info("🔄 Executing inference in thread pool (async)...")

        loop = asyncio.get_event_loop()
        results, visualization_data = await loop.run_in_executor(
            _executor,
            _run_inference_sync,
            input_data.data_source_url_or_path,
            input_data.data_definition,
            parameters,
        )

        load_time = time.time() - load_start
        logger.info(f"✅ Inference completed in {load_time:.2f}s (executed in thread pool)")

        total_time = time.time() - start_time

        logger.info("=" * 80)
        logger.info("✅ Inference request completed successfully")
        logger.info(f"   Total time: {total_time:.2f}s")
        logger.info(f"   Execution time: {load_time:.2f}s (async in thread pool)")
        logger.info(f"   Method: {results.get('method', 'unknown')}")
        logger.info("=" * 80)

        return InferenceOutput(
            prediction=results,
            visualization_data=visualization_data,
            execution_metadata={
                "total_time_seconds": round(total_time, 3),
                "execution_time_seconds": round(load_time, 3),
                "async_execution": True,
                "thread_pool": True,
                "model_version": "2.0.0",
                "api_version": "2.0.0",
            },
        )

    # --- Exception Handling (Phase 7: Improved) ---
    except (
        ModelNotInitializedError,
        timesfm_model_service.ModelNotInitializedError,
    ) as e:
        logger.error(f"❌ Model not initialized: {e}")
        # Let SapheneiaException handler in main.py handle this
        if isinstance(e, ModelNotInitializedError):
            raise e
        raise ModelNotInitializedError(str(e)) from e

    except (
        DataError,
        timesfm_data_service.TimesFMDataError,
        DataFetchError,
        CoreDataFetchError,
        ValueError,
    ) as e:
        logger.error(f"❌ Data error: {e}")
        # Let SapheneiaException handler handle structured errors
        if not isinstance(e, SapheneiaException):
            # Wrap in DataValidationError or DataFetchError
            if "not found" in str(e).lower() or "fetch" in str(e).lower():
                raise DataFetchError(str(e)) from e
            else:
                raise DataValidationError(str(e)) from e

    except SapheneiaException:
        # Already a structured error - let it pass through to handler
        raise

    except Exception:
        logger.exception("❌ Inference failed with unexpected error")
        # Generic errors will be caught by generic_exception_handler in main.py
        raise


# --- Shutdown Endpoint ---


@router.post("/shutdown", response_model=ShutdownOutput)
@limiter.limit(get_rate_limit("default"))
async def shutdown_model_endpoint(request: Request, response: Response):
    """
    Shutdown the TimesFM-2.0 model and free resources.

    This endpoint unloads the model from memory and performs cleanup.
    After shutdown, the model must be reinitialized before inference.

    **Returns:**
    - Shutdown confirmation message

    **Note:** This operation is immediate and cannot be undone.
    """
    logger.info("🔄 Received shutdown request")

    success = timesfm_model_service.shutdown_model()

    if success:
        logger.info("✅ Model shut down successfully")
        return ShutdownOutput(message="Model shut down successfully")
    else:
        logger.warning("⚠️  Model was not initialized or already shut down")
        return ShutdownOutput(message="Model was not initialized or already shut down")


# --- Canonical forecast contract -------------------------------------------
#
# ``/inference`` above requires `data_source_url_or_path` + `data_definition`
# and loads a CSV itself — a contract the orchestrator cannot satisfy, since it
# already holds the context series in memory. That mismatch meant every
# orchestrator call to this family was a hard 422 and the "timesfm" branch was
# effectively dead.
#
# The underlying service function `run_inference(target_inputs, ...)` already
# accepts raw series, so this endpoint is a thin adapter over it that speaks the
# same canonical contract as chronos. Both families now return one shape.


def _container_model_id() -> str | None:
    """The model this container is pinned to serve, or None if unpinned.

    Deliberately reads MODEL_VARIANT — the same variable chronos uses — rather
    than TIMESFM20_DEFAULT_CHECKPOINT. Every container mounts *both* family
    routers, so a family that derives its identity from a defaulted setting can
    never report "unpinned": the mismatch check below would pass on any
    container, and a chronos box asked for a TimesFM model would start loading
    a 500M checkpoint. Returning None here makes that a 503 instead.

    TIMESFM20_DEFAULT_CHECKPOINT remains the default for the legacy /inference
    path, which does not route by model identity.
    """
    return os.getenv("MODEL_VARIANT") or None


def _timesfm_quantile_bands(results: dict[str, Any], horizon: int) -> list[QuantileBand]:
    """Extract decile bands from TimesFM's quantile_forecast array.

    TimesFM returns shape (batch, horizon, 10) where index 0 is the mean and
    indices 1..9 are deciles 0.1 .. 0.9.
    """
    raw = results.get("quantile_forecast")
    if raw is None:
        return []
    arr = np.asarray(raw)
    if arr.ndim != 3 or arr.shape[0] < 1 or arr.shape[2] < 10:
        logger.warning("Unexpected quantile_forecast shape %s; omitting bands", arr.shape)
        return []
    bands = []
    for idx in range(1, 10):
        bands.append(
            QuantileBand(
                quantile=idx / 10.0,
                values=[float(v) for v in arr[0, :horizon, idx]],
            )
        )
    return bands


@router.post("/forecast", response_model=ForecastEnvelope)
@limiter.limit(get_rate_limit("inference"))
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
            detail="This container has no MODEL_VARIANT configured; it cannot serve forecasts.",
        )
    if payload.model_id and payload.model_id != served:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Model mismatch: this container serves {served!r} but the request "
                f"asked for {payload.model_id!r}. Route to that model's container."
            ),
        )

    status, _ = timesfm_model_service.get_status()
    if status == "uninitialized":
        logger.info("Lazy initializing TimesFM %s", served)
        await asyncio.get_running_loop().run_in_executor(
            _executor,
            lambda: timesfm_model_service.initialize_model(
                source_type="hf",
                checkpoint=served,
                horizon_len=max(payload.prediction_length, settings.TIMESFM20_DEFAULT_HORIZON_LEN),
            ),
        )
        status, _ = timesfm_model_service.get_status()
    if status != "ready":
        raise HTTPException(status_code=503, detail=f"Model not ready (status: {status})")

    start = time.time()
    results = await asyncio.get_running_loop().run_in_executor(
        _executor,
        lambda: timesfm_model_service.run_inference(
            target_inputs=[list(payload.context)],
            covariates=None,
            parameters={
                "use_covariates": False,
                "use_quantiles": True,
                "horizon_len": payload.prediction_length,
            },
        ),
    )
    elapsed = time.time() - start

    point = np.asarray(results.get("point_forecast"))
    if point.size == 0:
        raise HTTPException(status_code=500, detail="TimesFM returned an empty point_forecast")
    if point.ndim > 1:
        point = point[0]
    median = [float(v) for v in point[: payload.prediction_length]]

    return ForecastEnvelope(
        model_id=served,
        family=ModelFamily.TIMESFM.value,
        median=median,
        quantiles=_timesfm_quantile_bands(results, payload.prediction_length),
        metadata={
            "inference_time_seconds": round(elapsed, 3),
            "context_length": len(payload.context),
            "prediction_length": payload.prediction_length,
            "method": results.get("method"),
        },
    )
