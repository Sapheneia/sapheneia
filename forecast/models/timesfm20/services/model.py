"""
TimesFM-2.0 Model Service

Handles model initialization, state management, and inference execution.
Uses core modules for clean architecture.
"""

import os
import logging
import time
import threading
import numpy as np
from typing import Tuple, Optional, Any, List, Dict, Union

# Import core modules (proper Python imports - no sys.path hacks)
from ....core.model_wrapper import TimesFMModel
from ....core.forecasting import Forecaster, run_forecast, process_quantile_bands
from ....core.config import settings

logger = logging.getLogger(__name__)


# --- Custom Exceptions ---
# Updated to use centralized exception hierarchy (Phase 7: Error Handling)

# Import from centralized exceptions module
try:
    from ...core.exceptions import ModelNotInitializedError, ModelInitializationError
except ImportError:
    # Fallback if exceptions module not available
    class ModelNotInitializedError(Exception):
        """Raised when inference is attempted on uninitialized model."""
        pass

    class ModelInitializationError(Exception):
        """Raised when model initialization fails."""
        pass


# --- Module-Level State Management ---
# For single-worker deployment, we store the model state at module level
# Thread lock ensures safe concurrent access to module-level state

_forecaster_instance: Optional[Forecaster] = None
_model_wrapper: Optional[TimesFMModel] = None
_model_status: str = "uninitialized"  # "uninitialized", "initializing", "ready", "error"
_error_message: Optional[str] = None
_model_source_info: Optional[str] = None
_model_config: Optional[Dict[str, Any]] = None

# Thread lock for state access (prevents race conditions)
_model_lock = threading.Lock()


# --- File Path Handling ---

# Define base directory for local model artifacts relative to this file's location
BASE_LOCAL_MODEL_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'local')
)
logger.info(f"Base directory for TimesFM local models: {BASE_LOCAL_MODEL_DIR}")
os.makedirs(BASE_LOCAL_MODEL_DIR, exist_ok=True)


# --- Initialization Functions ---

def initialize_model(
    source_type: str = "hf",  # 'hf', 'local', 'mlflow'
    backend: str = None,
    context_len: int = None,
    horizon_len: int = None,
    checkpoint: Optional[str] = None,
    local_model_path: Optional[str] = None,
    mlflow_model_name: Optional[str] = None,
    mlflow_model_stage: str = "Production"
) -> None:
    """
    Initialize TimesFM model from specified source.

    This function loads the model into memory and prepares it for inference.
    It's a blocking operation that must complete before inference can proceed.

    Args:
        source_type: Source type ('hf', 'local', 'mlflow')
        backend: Computing backend ('cpu', 'gpu', 'tpu')
        context_len: Context window length
        horizon_len: Forecast horizon length
        checkpoint: HuggingFace repo ID
        local_model_path: Local model file path (relative to local/ dir)
        mlflow_model_name: MLflow model name
        mlflow_model_stage: MLflow model stage

    Raises:
        ModelInitializationError: If initialization fails
    """
    global _model_status, _error_message, _forecaster_instance, _model_wrapper
    global _model_source_info, _model_config

    # Thread-safe status check and update
    with _model_lock:
        # Check if already initialized
        if _model_status == "ready":
            logger.warning("Initialize called but model is already ready")
            return

        if _model_status == "initializing":
            raise ModelInitializationError("Initialization already in progress")

        # Mark as initializing
        _model_status = "initializing"
        _error_message = None

    # Set defaults from settings
    backend = backend or settings.TIMESFM20_DEFAULT_BACKEND
    context_len = context_len or settings.TIMESFM20_DEFAULT_CONTEXT_LEN
    horizon_len = horizon_len or settings.TIMESFM20_DEFAULT_HORIZON_LEN

    start_time = time.time()

    logger.info("=" * 80)
    logger.info(f"🚀 Starting TimesFM-2.0 initialization (source: {source_type})")
    logger.info(f"   Backend: {backend}")
    logger.info(f"   Context Length: {context_len}")
    logger.info(f"   Horizon Length: {horizon_len}")
    logger.info("=" * 80)

    try:
        if source_type == "hf":
            _initialize_from_hf(backend, context_len, horizon_len, checkpoint)

        elif source_type == "local":
            _initialize_from_local(backend, context_len, horizon_len, local_model_path)

        elif source_type == "mlflow":
            if not mlflow_model_name:
                raise ValueError("'mlflow_model_name' required for source_type 'mlflow'")
            _initialize_from_mlflow(
                mlflow_model_name, mlflow_model_stage,
                backend, context_len, horizon_len
            )

        else:
            raise ValueError(
                f"Unknown source_type: {source_type}. "
                f"Choose 'hf', 'local', or 'mlflow'"
            )

        # Store configuration and update status (thread-safe)
        with _model_lock:
            _model_config = {
                "source_type": source_type,
                "backend": backend,
                "context_len": context_len,
                "horizon_len": horizon_len,
                "checkpoint": checkpoint,
                "local_model_path": local_model_path
            }
            _model_status = "ready"

        elapsed = time.time() - start_time

        logger.info("=" * 80)
        logger.info(f"✅ TimesFM-2.0 initialization complete!")
        logger.info(f"   Time: {elapsed:.2f}s")
        logger.info(f"   Source: {_model_source_info}")
        logger.info("=" * 80)

    except Exception as e:
        # Update error state (thread-safe)
        with _model_lock:
            _model_status = "error"
            _error_message = str(e)
            _forecaster_instance = None
            _model_wrapper = None

        logger.error("=" * 80)
        logger.error(f"❌ TimesFM-2.0 initialization failed: {e}")
        logger.error("=" * 80)

        raise ModelInitializationError(f"Model initialization failed: {e}")


def _initialize_from_hf(
    backend: str,
    context_len: int,
    horizon_len: int,
    checkpoint: Optional[str]
) -> None:
    """Initialize model from HuggingFace checkpoint."""
    global _forecaster_instance, _model_wrapper, _model_source_info

    checkpoint = checkpoint or settings.TIMESFM20_DEFAULT_CHECKPOINT

    if not checkpoint:
        raise ValueError("HuggingFace checkpoint must be specified")

    logger.info(f"Loading model from HuggingFace: {checkpoint}")

    # Create model wrapper
    _model_wrapper = TimesFMModel(
        backend=backend,
        context_len=context_len,
        horizon_len=horizon_len,
        checkpoint=checkpoint,
        local_model_path=None
    )

    # Load the model
    timesfm_model = _model_wrapper.load_model()

    # Create forecaster
    _forecaster_instance = Forecaster(timesfm_model)

    _model_source_info = f"hf:{checkpoint}"
    logger.info(f"✅ Model loaded from HuggingFace: {checkpoint}")


def _initialize_from_local(
    backend: str,
    context_len: int,
    horizon_len: int,
    local_model_path: Optional[str]
) -> None:
    """Initialize model from local checkpoint file."""
    global _forecaster_instance, _model_wrapper, _model_source_info

    if not local_model_path:
        raise ValueError("Local model path must be specified")

    # Construct absolute path safely
    full_local_path = os.path.abspath(
        os.path.join(BASE_LOCAL_MODEL_DIR, local_model_path)
    )

    # Security check: ensure path is within allowed directory
    if not full_local_path.startswith(BASE_LOCAL_MODEL_DIR):
        raise ValueError(
            f"Local path '{local_model_path}' resolves outside allowed "
            f"directory '{BASE_LOCAL_MODEL_DIR}'"
        )

    if not os.path.exists(full_local_path):
        raise FileNotFoundError(f"Local model path not found: {full_local_path}")

    logger.info(f"Loading model from local path: {full_local_path}")

    # Create model wrapper
    _model_wrapper = TimesFMModel(
        backend=backend,
        context_len=context_len,
        horizon_len=horizon_len,
        checkpoint=None,
        local_model_path=full_local_path
    )

    # Load the model
    timesfm_model = _model_wrapper.load_model()

    # Create forecaster
    _forecaster_instance = Forecaster(timesfm_model)

    _model_source_info = f"local:{local_model_path}"
    logger.info(f"✅ Model loaded from local path: {local_model_path}")


def _initialize_from_mlflow(
    mlflow_model_name: str,
    mlflow_model_stage: str,
    backend: str,
    context_len: int,
    horizon_len: int
) -> None:
    """Initialize model from MLflow Model Registry."""
    global _forecaster_instance, _model_wrapper, _model_source_info

    # This is a placeholder for MLflow integration
    # Full implementation will be done in Phase 10
    raise NotImplementedError(
        "MLflow model loading will be implemented in Phase 10. "
        "For now, please use HuggingFace or local checkpoints."
    )


# --- Status Functions ---

def get_status() -> Tuple[str, Optional[str]]:
    """
    Get current model status and error message (thread-safe).

    Returns:
        Tuple of (status, error_message)
    """
    with _model_lock:
        return _model_status, _error_message


def get_model_source_info() -> Optional[str]:
    """
    Get information about model source (thread-safe).

    Returns:
        String describing model source or None
    """
    with _model_lock:
        return _model_source_info


def get_model_config() -> Optional[Dict[str, Any]]:
    """
    Get current model configuration (thread-safe).

    Returns:
        Dictionary with model configuration or None
    """
    with _model_lock:
        if _model_wrapper:
            return _model_wrapper.get_model_info()
        return _model_config


# --- Inference Functions ---

def run_inference(
    target_inputs: List[List[float]],
    covariates: Optional[Dict[str, Any]],
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run TimesFM inference on provided data.

    Args:
        target_inputs: Target time series data (as list of lists for batching)
        covariates: Optional covariates dictionary
        parameters: Inference parameters (use_covariates, use_quantiles, etc.)

    Returns:
        Dictionary containing inference results

    Raises:
        ModelNotInitializedError: If model is not ready
        Exception: If inference fails
    """
    global _forecaster_instance, _model_status

    # Check model status (thread-safe)
    with _model_lock:
        if _model_status != "ready" or _forecaster_instance is None:
            logger.error("Inference called but model not ready")
            raise ModelNotInitializedError(
                f"Model is not initialized or in an error state. Status: {_model_status}"
            )
        # Get forecaster reference while holding lock
        forecaster = _forecaster_instance

    logger.info("=" * 80)
    logger.info("🚀 Starting TimesFM inference")
    logger.info(f"   Target inputs shape: {[len(x) for x in target_inputs] if target_inputs else 'None'}")
    logger.info(f"   Covariates provided: {bool(covariates and any(covariates.values()))}")
    logger.info(f"   Parameters: {parameters}")
    logger.info("=" * 80)

    try:
        # Extract parameters
        use_covariates = parameters.get('use_covariates', False)
        freq = parameters.get('freq', 0)

        # Run forecast using existing function
        results = run_forecast(
            forecaster=forecaster,
            target_inputs=target_inputs,
            covariates=covariates if use_covariates else None,
            use_covariates=use_covariates and bool(covariates and any(covariates.values())),
            freq=freq
        )

        # Process quantile bands if requested
        quantile_indices = parameters.get('quantile_indices', [1, 3, 5, 7, 9])
        if 'quantile_forecast' in results and quantile_indices is not None:
            logger.info(f"Processing quantile bands with indices: {quantile_indices}")
            quantile_bands = process_quantile_bands(
                quantile_forecast=results['quantile_forecast'],
                selected_indices=quantile_indices
            )
            results['quantile_bands'] = quantile_bands

        logger.info("=" * 80)
        logger.info("✅ TimesFM inference completed successfully")
        logger.info(f"   Method: {results.get('method', 'unknown')}")
        logger.info(f"   Point forecast shape: {np.array(results.get('point_forecast', [])).shape}")
        logger.info(f"   Quantile forecast shape: {np.array(results.get('quantile_forecast', [])).shape}")
        logger.info("=" * 80)

        return results

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ TimesFM inference failed: {str(e)}")
        logger.error("=" * 80)
        raise


# --- Shutdown Functions ---

def shutdown_model() -> bool:
    """
    Shutdown the model and free resources.

    Returns:
        True if shutdown successful, False if nothing to shutdown
    """
    global _forecaster_instance, _model_wrapper, _model_status
    global _error_message, _model_source_info, _model_config

    # Thread-safe shutdown
    with _model_lock:
        if _forecaster_instance is None and _model_status == "uninitialized":
            logger.warning("Shutdown called but model was not initialized")
            return False

        logger.info("=" * 80)
        logger.info(f"🔄 Shutting down TimesFM model")
        logger.info(f"   Source: {_model_source_info}")
        logger.info("=" * 80)

        # Cleanup (add specific cleanup if needed, e.g., GPU memory)
        _forecaster_instance = None
        _model_wrapper = None
        _model_status = "uninitialized"
        _error_message = None
        _model_source_info = None
        _model_config = None

    logger.info("✅ TimesFM model shut down successfully")
    return True
