"""
Chronos API Schemas

Pydantic models for request/response validation.
"""

from typing import Any

from pydantic import BaseModel, Field


class ModelInitInput(BaseModel):
    """Model initialization request schema."""

    model_variant: str | None = Field(
        default=None,
        description="Chronos model variant (e.g., 'amazon/chronos-t5-tiny'). "
        "If not provided, uses MODEL_VARIANT environment variable.",
    )
    device: str | None = Field(
        default="cpu", description="Device to load model on ('cpu', 'cuda', 'mps')"
    )

    class Config:
        json_schema_extra = {
            "example": {"model_variant": "amazon/chronos-t5-tiny", "device": "cpu"}
        }


class ModelInitOutput(BaseModel):
    """Model initialization response schema."""

    message: str
    model_status: str
    model_info: dict[str, Any] | None = None


class StatusOutput(BaseModel):
    """Model status response schema."""

    model_status: str
    details: str | None = None


class InferenceInput(BaseModel):
    """Inference request schema."""

    context: list[float] = Field(..., description="Historical time series values for context")
    prediction_length: int = Field(..., description="Number of time steps to forecast", gt=0)
    num_samples: int | None = Field(
        default=20, description="Number of sample trajectories to generate", gt=0
    )
    temperature: float | None = Field(default=1.0, description="Sampling temperature", gt=0)
    top_k: int | None = Field(default=50, description="Top-k sampling parameter", gt=0)
    top_p: float | None = Field(
        default=1.0, description="Top-p (nucleus) sampling parameter", gt=0, le=1.0
    )

    class Config:
        json_schema_extra = {
            "example": {
                "context": [1.0, 2.0, 3.0, 4.0, 5.0],
                "prediction_length": 10,
                "num_samples": 20,
            }
        }


class InferenceOutput(BaseModel):
    """Inference response schema."""

    prediction: dict[str, Any] = Field(
        ..., description="Forecast results including median, quantiles, and samples"
    )
    execution_metadata: dict[str, Any] = Field(
        ..., description="Execution metadata (timing, model version, etc.)"
    )


class ShutdownOutput(BaseModel):
    """Shutdown response schema."""

    message: str
