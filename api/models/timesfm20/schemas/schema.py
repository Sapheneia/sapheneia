"""
Pydantic Schemas for TimesFM-2.0 API

Defines request and response models for all TimesFM-2.0 endpoints with
comprehensive validation and documentation.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, Any, List, Union, Generic, TypeVar
from datetime import datetime


# --- Initialization Schemas ---

class ModelInitInput(BaseModel):
    """
    Input schema for model initialization endpoint.

    Supports initialization from HuggingFace, local path, or MLflow.
    """

    backend: str = Field(
        default="cpu",
        description="Computing backend: 'cpu', 'gpu', or 'tpu'",
        examples=["cpu", "gpu"],
        pattern="^(cpu|gpu|tpu)$"
    )

    context_len: int = Field(
        default=64,
        ge=32,
        le=2048,
        description="Context window length (32-2048)",
        examples=[64, 100, 512]
    )

    horizon_len: int = Field(
        default=24,
        ge=1,
        le=128,
        description="Forecast horizon length (1-128)",
        examples=[24, 48, 96]
    )

    checkpoint: Optional[str] = Field(
        default="google/timesfm-2.0-500m-pytorch",
        description="HuggingFace checkpoint repo ID",
        examples=["google/timesfm-2.0-500m-pytorch", "google/timesfm-2.0-500m-jax"]
    )

    local_model_path: Optional[str] = Field(
        default=None,
        description="Relative path to local model file (within api/timesfm20/local/)",
        examples=["model.ckpt", "checkpoints/timesfm_v2.pt"]
    )

    @field_validator('backend')
    @classmethod
    def validate_backend(cls, v: str) -> str:
        """Validate backend is one of allowed values."""
        allowed = ['cpu', 'gpu', 'tpu', 'mps']
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"Backend must be one of {allowed}")
        return v_lower

    class Config:
        json_schema_extra = {
            "example": {
                "backend": "cpu",
                "context_len": 64,
                "horizon_len": 24,
                "checkpoint": "google/timesfm-2.0-500m-pytorch"
            }
        }


class ModelInitOutput(BaseModel):
    """Output schema for model initialization endpoint."""

    message: str
    model_status: str

    model_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detailed model information"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Model initialized successfully",
                "model_status": "ready",
                "model_info": {
                    "backend": "cpu",
                    "context_len": 64,
                    "horizon_len": 24,
                    "source": "hf:google/timesfm-2.0-500m-pytorch"
                }
            }
        }


# --- Status Schemas ---

class StatusOutput(BaseModel):
    """Output schema for status endpoint."""

    model_status: str

    details: Optional[str] = Field(
        default=None,
        description="Additional status details"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "model_status": "ready",
                "details": "Source: hf:google/timesfm-2.0-500m-pytorch"
            }
        }


# --- Inference Schemas ---

class InferenceInput(BaseModel):
    """
    Input schema for inference endpoint.

    Supports data from local files or URLs with comprehensive parameter configuration.
    """

    data_source_url_or_path: str = Field(
        ...,
        description="URL or path to the data source",
        min_length=1,
        max_length=1024,
        examples=["data.csv", "http://example.com/data.csv"]
    )
    
    data_definition: Dict[str, str] = Field(
        ...,
        description="Column definitions mapping column names to types",
        min_length=1,
        examples=[{"price": "target", "volume": "dynamic_numerical"}]
    )

    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Inference parameters (context_len, horizon_len, use_covariates, etc.)"
    )

    @field_validator('data_definition')
    @classmethod
    def validate_data_definition(cls, v):
        """Validate data definition structure."""
        allowed_types = {
            'target', 'dynamic_numerical', 'dynamic_categorical',
            'static_numerical', 'static_categorical'
        }

        # Must have exactly one target
        targets = [k for k, typ in v.items() if typ == 'target']
        if len(targets) == 0:
            raise ValueError("data_definition must have at least one 'target' column")

        # Validate all types
        for col, typ in v.items():
            if typ not in allowed_types:
                raise ValueError(
                    f"Invalid type '{typ}' for column '{col}'. "
                    f"Allowed: {allowed_types}"
                )

        return v

    @field_validator('parameters')
    @classmethod
    def validate_parameters(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parameters structure."""
        if 'context_len' in v:
            context = v['context_len']
            if not isinstance(context, int) or context < 1:
                raise ValueError("context_len must be positive integer")

        if 'horizon_len' in v:
            horizon = v['horizon_len']
            if not isinstance(horizon, int) or horizon < 1:
                raise ValueError("horizon_len must be positive integer")

        if 'quantiles' in v:
            quantiles = v['quantiles']
            if not isinstance(quantiles, list):
                raise ValueError("quantiles must be a list")
            for q in quantiles:
                if not (0 < q < 1):
                    raise ValueError(f"quantile {q} must be between 0 and 1")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "data_source_url_or_path": "local://data/sample_data.csv",
                "data_definition": {
                    "price": "target",
                    "volume": "dynamic_numerical",
                    "category": "dynamic_categorical"
                },
                "parameters": {
                    "context_len": 64,
                    "horizon_len": 24,
                    "use_covariates": True,
                    "use_quantiles": True,
                    "quantile_indices": [1, 3, 5, 7, 9],
                    "context_start_date": "2024-01-01",
                    "context_end_date": "2024-03-31"
                }
            }
        }


class InferenceOutput(BaseModel):
    """Output schema for inference endpoint."""

    prediction: Dict[str, Any]

    visualization_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Data prepared for visualization"
    )
    
    execution_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Execution metadata (timing, model version, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "prediction": {
                    "point_forecast": [100.2, 101.5, 102.3],
                    "quantile_forecast": [[...], [...], [...]],
                    "metadata": {
                        "method": "covariates_enhanced",
                        "context_length": 64,
                        "horizon_length": 24,
                        "covariates_used": True
                    }
                },
                "visualization_data": {
                    "historical_data": [...],
                    "dates_historical": [...],
                    "dates_future": [...]
                },
                "execution_metadata": {
                    "total_time_seconds": 2.34,
                    "load_time_seconds": 0.12,
                    "inference_time_seconds": 1.95,
                    "model_version": "2.0.0",
                    "api_version": "2.0.0"
                }
            }
        }


# --- Shutdown Schemas ---

class ShutdownOutput(BaseModel):
    """Output schema for shutdown endpoint."""

    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Model shut down successfully"
            }
        }


# --- Response Wrapper Schemas (Phase 5: API Improvements) ---

T = TypeVar('T')


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper for consistent structure."""
    
    success: bool = Field(
        description="Whether the request was successful"
    )
    
    data: Optional[T] = Field(
        default=None,
        description="Response data"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if not successful"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )


# --- Pagination Schemas ---

class PaginationParams(BaseModel):
    """Pagination parameters for endpoints returning multiple items."""
    
    page: int = Field(
        default=1,
        ge=1,
        description="Page number"
    )
    
    page_size: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Items per page"
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper for list endpoints."""
    
    items: List[T] = Field(
        description="Items for current page"
    )
    
    total: int = Field(
        description="Total number of items"
    )
    
    page: int = Field(
        description="Current page number"
    )
    
    page_size: int = Field(
        description="Number of items per page"
    )
    
    total_pages: int = Field(
        description="Total number of pages"
    )
