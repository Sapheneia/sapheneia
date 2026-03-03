"""
TiRex Model Service

Handles model initialization, state management, and inference execution.
Uses HuggingFace cache for model loading.
"""

import os
import logging
import time
import threading
import torch
from typing import Tuple, Optional, Any, List, Dict
try:
    from tirex import load_model, ForecastModel
except ImportError:
    # Handle the case during model build where the library isn't available
    load_model = None
    ForecastModel = None

logger = logging.getLogger(__name__)


# --- Custom Exceptions ---
class ModelNotInitializedError(Exception):
    """Raised when inference is attempted on uninitialized model."""
    pass


class ModelInitializationError(Exception):
    """Raised when model initialization fails."""
    pass


# --- Module-Level State Management ---
# For single-worker deployment, store model state at module level
_model: Optional[Any] = None
_model_status: str = "uninitialized"  # "ready", "error", etc.
_error_message: Optional[str] = None
_model_variant: Optional[str] = None
_device: str = "cpu"
_model_lock = threading.Lock()


def initialize_model(
    model_variant: Optional[str] = None,
    device: Optional[str] = None
) -> None:
    """
    Initialize TiRex model from HuggingFace cache.

    Args:
        model_variant: Model identifier (e.g., 'NX-AI/TiRex')
                      If None, uses MODEL_VARIANT environment variable.
        device: Device to load on ('cpu', 'cuda', 'mps'). Defaults to 'cpu'.

    Raises:
        ModelInitializationError: If initialization fails
    """
    global _model, _model_status, _error_message, _model_variant, _device

    if load_model is None:
        raise ModelInitializationError("tirex library not installed")

    with _model_lock:
        if _model_status == "ready":
            logger.warning("Model already initialized")
            return

        if _model_status == "initializing":
            raise ModelInitializationError(
                "Initialization already in progress"
            )

        _model_status = "initializing"
        _error_message = None

    # Determine model variant
    if model_variant is None:
        model_variant = os.getenv("MODEL_VARIANT", "NX-AI/TiRex")

    if not model_variant:
        raise ValueError(
            "model_variant must be provided or "
            "MODEL_VARIANT env var must be set"
        )

    # Determine device
    if device is None:
        device = os.getenv("DEVICE", "cpu")

    start_time = time.time()

    logger.info("=" * 80)
    logger.info("🚀 Starting TiRex initialization")
    logger.info(f"   Model Variant: {model_variant}")
    logger.info(f"   Device: {device}")
    logger.info(f"   HF_HOME: {os.getenv('HF_HOME', 'default')}")
    logger.info("=" * 80)

    try:
        # Load model from HuggingFace cache
        # The cache is automatically used if HF_HOME is set
        # TiRex defaults to bf16 inside its own class, let it handle the map
        model = load_model(model_variant)
        # Move model to device
        model = model.to(device)

        # Update state
        with _model_lock:
            _model = model
            _model_variant = model_variant
            _device = device
            _model_status = "ready"

        elapsed = time.time() - start_time

        logger.info("=" * 80)
        logger.info("✅ TiRex initialization complete!")
        logger.info(f"   Time: {elapsed:.2f}s")
        logger.info(f"   Model: {model_variant}")
        logger.info("=" * 80)

    except Exception as e:
        with _model_lock:
            _model_status = "error"
            _error_message = str(e)
            _model = None

        logger.error("=" * 80)
        logger.error(f"❌ TiRex initialization failed: {e}")
        logger.error("=" * 80)

        raise ModelInitializationError(f"Model initialization failed: {e}")


def get_status() -> Tuple[str, Optional[str]]:
    """
    Get current model status (thread-safe).

    Returns:
        Tuple of (status, error_message)
    """
    with _model_lock:
        return _model_status, _error_message


def get_model_info() -> Optional[Dict[str, Any]]:
    """
    Get model information (thread-safe).

    Returns:
        Dictionary with model info or None
    """
    with _model_lock:
        if _model is None:
            return None

        return {
            "model_variant": _model_variant,
            "device": _device,
            "status": _model_status
        }


def run_inference(
    context: List[float],
    prediction_length: int
) -> Dict[str, Any]:
    """
    Run TiRex inference on provided context.

    Args:
        context: Historical time series values
        prediction_length: Number of steps to forecast

    Returns:
        Dictionary containing forecast results

    Raises:
        ModelNotInitializedError: If model is not ready
    """
    global _model, _model_status

    # Check model status
    with _model_lock:
        if _model_status != "ready" or _model is None:
            raise ModelNotInitializedError(
                f"Model not initialized. Status: {_model_status}"
            )
        model = _model

    logger.info("=" * 80)
    logger.info("🚀 Starting TiRex inference")
    logger.info(f"   Context length: {len(context)}")
    logger.info(f"   Prediction length: {prediction_length}")
    logger.info("=" * 80)

    start_time = time.time()

    try:
        # Convert context to tensor
        # TiRex requires a tensor of shape (batch, history_len)
        context_tensor = torch.tensor(
            [context], dtype=torch.float32
        ).to(_device)

        # Run forecast
        # TiRex handles arbitrary forecasting horizons internally in one call
        # The method returns a tuple: (quantiles, mean)
        quantiles, mean_forecast = model.forecast(
            context_tensor, prediction_length=prediction_length
        )

        # Result has shape (batch, prediction_length)
        point_forecast = mean_forecast.cpu().detach().numpy()[0].tolist()

        elapsed = time.time() - start_time

        logger.info("=" * 80)
        logger.info("✅ TiRex inference completed")
        logger.info(f"   Time: {elapsed:.2f}s")
        logger.info(f"   Forecast length: {len(point_forecast)}")
        logger.info("=" * 80)

        return {
            "point_forecast": point_forecast,
            "metadata": {
                "context_length": len(context),
                "prediction_length": prediction_length,
                "model_variant": _model_variant,
                "inference_time_seconds": round(elapsed, 3)
            }
        }

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ TiRex inference failed: {e}")
        logger.error("=" * 80)
        raise


def shutdown_model() -> bool:
    """
    Shutdown the model and free resources.

    Returns:
        True if shutdown successful
    """
    global _model, _model_status, _error_message, _model_variant, _device

    with _model_lock:
        if _model is None:
            logger.warning("Model was not initialized")
            return False

        logger.info("=" * 80)
        logger.info("🔄 Shutting down TiRex model")
        logger.info(f"   Model: {_model_variant}")
        logger.info("=" * 80)

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        _model = None
        _model_status = "uninitialized"
        _error_message = None
        _model_variant = None
        _device = "cpu"

    logger.info("✅ TiRex model shut down successfully")
    return True
