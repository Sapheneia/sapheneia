"""
Sapheneia Model Registry

Central registry for all forecasting models available in the API.
Each model is a separate module under forecast/models/ with its own routes and services.
"""

from typing import Dict, Any, List

# Model registry - maps model name to module information
MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "timesfm20": {
        "name": "TimesFM 2.0",
        "version": "2.0.500m",
        "description": "Google's TimesFM 2.0 - 500M parameter foundation model for time series forecasting",
        "module": "forecast.models.timesfm20",
        "router_path": "forecast.models.timesfm20.routes.endpoints",
        "service_path": "forecast.models.timesfm20.services.model",
        "default_port": 8001,
        "status": "active"
    },
    # Future models can be added here:
    # "chronos": {
    #     "name": "Chronos",
    #     "version": "1.0",
    #     "description": "Amazon's Chronos - Transformer-based forecasting model",
    #     "module": "forecast.models.chronos",
    #     "router_path": "forecast.models.chronos.routes.endpoints",
    #     "service_path": "forecast.models.chronos.services.model",
    #     "default_port": 8002,
    #     "status": "planned"
    # },
}


def get_available_models() -> List[str]:
    """
    Get list of available model names.

    Returns:
        List of model identifiers
    """
    return [
        model_id for model_id, config in MODEL_REGISTRY.items()
        if config.get("status") == "active"
    ]


def get_model_info(model_id: str) -> Dict[str, Any]:
    """
    Get information about a specific model.

    Args:
        model_id: Model identifier (e.g., "timesfm20")

    Returns:
        Model configuration dictionary

    Raises:
        KeyError: If model_id not found in registry
    """
    if model_id not in MODEL_REGISTRY:
        raise KeyError(f"Model '{model_id}' not found in registry")

    return MODEL_REGISTRY[model_id]


def get_all_models_info() -> Dict[str, Dict[str, Any]]:
    """
    Get information about all registered models.

    Returns:
        Complete model registry
    """
    return MODEL_REGISTRY.copy()
