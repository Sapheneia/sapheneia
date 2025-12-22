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
    # Amazon Chronos Models
    "chronos-t5-tiny": {
        "name": "Chronos T5 Tiny",
        "version": "1.0",
        "description": "Amazon Chronos T5 Tiny - Compact time series forecasting model",
        "module": "forecast.models.chronos",
        "router_path": "forecast.models.chronos.routes.endpoints",
        "service_path": "forecast.models.chronos.services.model",
        "default_port": 8100,
        "huggingface_id": "amazon/chronos-t5-tiny",
        "status": "active"
    },
    "chronos-t5-mini": {
        "name": "Chronos T5 Mini",
        "version": "1.0",
        "description": "Amazon Chronos T5 Mini - Small time series forecasting model",
        "module": "forecast.models.chronos",
        "router_path": "forecast.models.chronos.routes.endpoints",
        "service_path": "forecast.models.chronos.services.model",
        "default_port": 8101,
        "huggingface_id": "amazon/chronos-t5-mini",
        "status": "active"
    },
    "chronos-t5-small": {
        "name": "Chronos T5 Small",
        "version": "1.0",
        "description": "Amazon Chronos T5 Small - Medium time series forecasting model",
        "module": "forecast.models.chronos",
        "router_path": "forecast.models.chronos.routes.endpoints",
        "service_path": "forecast.models.chronos.services.model",
        "default_port": 8102,
        "huggingface_id": "amazon/chronos-t5-small",
        "status": "active"
    },
    "chronos-t5-base": {
        "name": "Chronos T5 Base",
        "version": "1.0",
        "description": "Amazon Chronos T5 Base - Base time series forecasting model",
        "module": "forecast.models.chronos",
        "router_path": "forecast.models.chronos.routes.endpoints",
        "service_path": "forecast.models.chronos.services.model",
        "default_port": 8103,
        "huggingface_id": "amazon/chronos-t5-base",
        "status": "active"
    },
    "chronos-t5-large": {
        "name": "Chronos T5 Large",
        "version": "1.0",
        "description": "Amazon Chronos T5 Large - Large time series forecasting model",
        "module": "forecast.models.chronos",
        "router_path": "forecast.models.chronos.routes.endpoints",
        "service_path": "forecast.models.chronos.services.model",
        "default_port": 8104,
        "huggingface_id": "amazon/chronos-t5-large",
        "status": "active"
    },
    "chronos-bolt-mini": {
        "name": "Chronos Bolt Mini",
        "version": "1.0",
        "description": "Amazon Chronos Bolt Mini - Fast mini forecasting model",
        "module": "forecast.models.chronos",
        "router_path": "forecast.models.chronos.routes.endpoints",
        "service_path": "forecast.models.chronos.services.model",
        "default_port": 8105,
        "huggingface_id": "amazon/chronos-bolt-mini",
        "status": "active"
    },
    "chronos-bolt-small": {
        "name": "Chronos Bolt Small",
        "version": "1.0",
        "description": "Amazon Chronos Bolt Small - Fast small forecasting model",
        "module": "forecast.models.chronos",
        "router_path": "forecast.models.chronos.routes.endpoints",
        "service_path": "forecast.models.chronos.services.model",
        "default_port": 8106,
        "huggingface_id": "amazon/chronos-bolt-small",
        "status": "active"
    },
    "chronos-bolt-base": {
        "name": "Chronos Bolt Base",
        "version": "1.0",
        "description": "Amazon Chronos Bolt Base - Fast base forecasting model",
        "module": "forecast.models.chronos",
        "router_path": "forecast.models.chronos.routes.endpoints",
        "service_path": "forecast.models.chronos.services.model",
        "default_port": 8107,
        "huggingface_id": "amazon/chronos-bolt-base",
        "status": "active"
    },
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
