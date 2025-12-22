"""
Chronos Model Service

Handles model initialization, state management, and inference execution.
Uses HuggingFace cache for model loading.
"""

import os
import logging
import time
import threading
import torch
import numpy as np
from typing import Tuple, Optional, Any, List, Dict
from chronos import ChronosPipeline

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
_pipeline: Optional[ChronosPipeline] = None
_model_status: str = "uninitialized"  # "uninitialized", "initializing", "ready", "error"
_error_message: Optional[str] = None
_model_variant: Optional[str] = None
_device: str = "cpu"
_model_lock = threading.Lock()


def initialize_model(
    model_variant: Optional[str] = None,
    device: Optional[str] = None
) -> None:
    """
    Initialize Chronos model from HuggingFace cache.

    Args:
        model_variant: Model identifier (e.g., 'amazon/chronos-t5-tiny')
                      If None, uses MODEL_VARIANT environment variable.
        device: Device to load on ('cpu', 'cuda', 'mps'). Defaults to 'cpu'.

    Raises:
        ModelInitializationError: If initialization fails
    """
    global _pipeline, _model_status, _error_message, _model_variant, _device

    with _model_lock:
        if _model_status == "ready":
            logger.warning("Model already initialized")
            return

        if _model_status == "initializing":
            raise ModelInitializationError("Initialization already in progress")

        _model_status = "initializing"
        _error_message = None

    # Determine model variant
    if model_variant is None:
        model_variant = os.getenv("MODEL_VARIANT")

    if not model_variant:
        raise ValueError(
            "model_variant must be provided or MODEL_VARIANT env var must be set"
        )

    # Determine device
    if device is None:
        device = os.getenv("DEVICE", "cpu")

    start_time = time.time()

    logger.info("=" * 80)
    logger.info(f"🚀 Starting Chronos initialization")
    logger.info(f"   Model Variant: {model_variant}")
    logger.info(f"   Device: {device}")
    logger.info(f"   HF_HOME: {os.getenv('HF_HOME', 'default')}")
    logger.info("=" * 80)

    try:
        # Load model from HuggingFace cache
        # The cache is automatically used if HF_HOME is set
        pipeline = ChronosPipeline.from_pretrained(
            model_variant,
            device_map=device,
            torch_dtype=torch.bfloat16 if device != "cpu" else torch.float32,
        )

        # Update state
        with _model_lock:
            _pipeline = pipeline
            _model_variant = model_variant
            _device = device
            _model_status = "ready"

        elapsed = time.time() - start_time

        logger.info("=" * 80)
        logger.info(f"✅ Chronos initialization complete!")
        logger.info(f"   Time: {elapsed:.2f}s")
        logger.info(f"   Model: {model_variant}")
        logger.info("=" * 80)

    except Exception as e:
        with _model_lock:
            _model_status = "error"
            _error_message = str(e)
            _pipeline = None

        logger.error("=" * 80)
        logger.error(f"❌ Chronos initialization failed: {e}")
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
        if _pipeline is None:
            return None

        return {
            "model_variant": _model_variant,
            "device": _device,
            "status": _model_status
        }


def run_inference(
    context: List[float],
    prediction_length: int,
    num_samples: int = 20,
    temperature: float = 1.0,
    top_k: int = 50,
    top_p: float = 1.0
) -> Dict[str, Any]:
    """
    Run Chronos inference on provided context.

    Args:
        context: Historical time series values
        prediction_length: Number of steps to forecast
        num_samples: Number of sample trajectories
        temperature: Sampling temperature
        top_k: Top-k sampling parameter
        top_p: Top-p (nucleus) sampling parameter

    Returns:
        Dictionary containing forecast results

    Raises:
        ModelNotInitializedError: If model is not ready
    """
    global _pipeline, _model_status

    # Check model status
    with _model_lock:
        if _model_status != "ready" or _pipeline is None:
            raise ModelNotInitializedError(
                f"Model not initialized. Status: {_model_status}"
            )
        pipeline = _pipeline

    logger.info("=" * 80)
    logger.info("🚀 Starting Chronos inference")
    logger.info(f"   Context length: {len(context)}")
    logger.info(f"   Prediction length: {prediction_length}")
    logger.info(f"   Num samples: {num_samples}")
    logger.info("=" * 80)

    start_time = time.time()

    try:
        # Convert context to tensor
        context_tensor = torch.tensor([context])

        # Run forecast
        # Note: ChronosPipeline.predict() uses positional argument for context
        forecast = pipeline.predict(
            context_tensor,  # First positional argument
            prediction_length=prediction_length,
            num_samples=num_samples,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p
        )

        # Convert to numpy for easier manipulation
        forecast_np = forecast.numpy()  # Shape: (1, num_samples, prediction_length)

        # Calculate statistics
        median = np.median(forecast_np[0], axis=0).tolist()
        mean = np.mean(forecast_np[0], axis=0).tolist()

        # Calculate quantiles
        quantiles = {
            "10": np.quantile(forecast_np[0], 0.10, axis=0).tolist(),
            "20": np.quantile(forecast_np[0], 0.20, axis=0).tolist(),
            "30": np.quantile(forecast_np[0], 0.30, axis=0).tolist(),
            "40": np.quantile(forecast_np[0], 0.40, axis=0).tolist(),
            "50": median,  # 50th percentile = median
            "60": np.quantile(forecast_np[0], 0.60, axis=0).tolist(),
            "70": np.quantile(forecast_np[0], 0.70, axis=0).tolist(),
            "80": np.quantile(forecast_np[0], 0.80, axis=0).tolist(),
            "90": np.quantile(forecast_np[0], 0.90, axis=0).tolist(),
        }

        # All samples
        samples = forecast_np[0].tolist()  # Shape: (num_samples, prediction_length)

        elapsed = time.time() - start_time

        logger.info("=" * 80)
        logger.info("✅ Chronos inference completed")
        logger.info(f"   Time: {elapsed:.2f}s")
        logger.info(f"   Forecast shape: {forecast_np.shape}")
        logger.info("=" * 80)

        return {
            "median": median,
            "mean": mean,
            "quantiles": quantiles,
            "samples": samples,
            "metadata": {
                "context_length": len(context),
                "prediction_length": prediction_length,
                "num_samples": num_samples,
                "model_variant": _model_variant,
                "inference_time_seconds": round(elapsed, 3)
            }
        }

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Chronos inference failed: {e}")
        logger.error("=" * 80)
        raise


def shutdown_model() -> bool:
    """
    Shutdown the model and free resources.

    Returns:
        True if shutdown successful
    """
    global _pipeline, _model_status, _error_message, _model_variant, _device

    with _model_lock:
        if _pipeline is None:
            logger.warning("Model was not initialized")
            return False

        logger.info("=" * 80)
        logger.info(f"🔄 Shutting down Chronos model")
        logger.info(f"   Model: {_model_variant}")
        logger.info("=" * 80)

        _pipeline = None
        _model_status = "uninitialized"
        _error_message = None
        _model_variant = None
        _device = "cpu"

    logger.info("✅ Chronos model shut down successfully")
    return True
