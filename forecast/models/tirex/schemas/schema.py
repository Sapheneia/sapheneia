"""
TiRex API Schemas

Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List


class ModelInitInput(BaseModel):
    """Model initialization request schema."""
    model_variant: str = Field(
        default="NX-AI/TiRex",
        description="TiRex model variant (e.g., 'NX-AI/TiRex')"
    )
    device: Optional[str] = Field(
        default="cpu",
        description="Device to load model on ('cpu', 'cuda', 'mps')"
    )

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        if v not in ["cpu", "cuda", "mps"]:
            raise ValueError(f"Device '{v}' is not supported. Must be 'cpu', 'cuda', or 'mps'")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "model_variant": "NX-AI/TiRex",
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

    class Config:
        json_schema_extra = {
            "example": {
                "context": [1.0, 2.0, 3.0, 4.0, 5.0],
                "prediction_length": 10
            }
        }


class InferenceOutput(BaseModel):
    """Inference response schema."""
    prediction: Dict[str, Any] = Field(
        ...,
        description="Forecast results including point_forecast"
    )
    execution_metadata: Dict[str, Any] = Field(
        ...,
        description="Execution metadata (timing, model version, etc.)"
    )


class ShutdownOutput(BaseModel):
    """Shutdown response schema."""
    message: str
