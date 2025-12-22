"""
Chronos API Schemas

Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ModelInitInput(BaseModel):
    """Model initialization request schema."""
    model_variant: Optional[str] = Field(
        default=None,
        description="Chronos model variant (e.g., 'amazon/chronos-t5-tiny'). "
                    "If not provided, uses MODEL_VARIANT environment variable."
    )
    device: Optional[str] = Field(
        default="cpu",
        description="Device to load model on ('cpu', 'cuda', 'mps')"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "model_variant": "amazon/chronos-t5-tiny",
                "device": "cpu"
            }
        }


class ModelInitOutput(BaseModel):
    """Model initialization response schema."""
    message: str
    model_status: str
    model_info: Optional[Dict[str, Any]] = None


class StatusOutput(BaseModel):
    """Model status response schema."""
    model_status: str
    details: Optional[str] = None


class InferenceInput(BaseModel):
    """Inference request schema."""
    context: List[float] = Field(
        ...,
        description="Historical time series values for context"
    )
    prediction_length: int = Field(
        ...,
        description="Number of time steps to forecast",
        gt=0
    )
    num_samples: Optional[int] = Field(
        default=20,
        description="Number of sample trajectories to generate",
        gt=0
    )
    temperature: Optional[float] = Field(
        default=1.0,
        description="Sampling temperature",
        gt=0
    )
    top_k: Optional[int] = Field(
        default=50,
        description="Top-k sampling parameter",
        gt=0
    )
    top_p: Optional[float] = Field(
        default=1.0,
        description="Top-p (nucleus) sampling parameter",
        gt=0,
        le=1.0
    )

    class Config:
        json_schema_extra = {
            "example": {
                "context": [1.0, 2.0, 3.0, 4.0, 5.0],
                "prediction_length": 10,
                "num_samples": 20
            }
        }


class InferenceOutput(BaseModel):
    """Inference response schema."""
    prediction: Dict[str, Any] = Field(
        ...,
        description="Forecast results including median, quantiles, and samples"
    )
    execution_metadata: Dict[str, Any] = Field(
        ...,
        description="Execution metadata (timing, model version, etc.)"
    )


class ShutdownOutput(BaseModel):
    """Shutdown response schema."""
    message: str
