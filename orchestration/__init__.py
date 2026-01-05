"""
Orchestration Module

Unified orchestration layer connecting Aleutian (Go) to Sapheneia's
forecasting models. This module provides:
- Standardized request/response contracts with full metadata
- Model-agnostic inference routing
- Pure transformation adapters for each model family
- Data provenance tracking (source, period, timestamps)

Architecture:
    Aleutian (Go) -> /orchestration/v1/predict -> OrchestrationService -> Model Backends
"""

from .schema import (
    Period,
    DataSource,
    DataField,
    ContextData,
    HorizonSpec,
    ForecastData,
    InferenceRequest,
    InferenceResponse,
    ContextSummary,
    InferenceMetadata,
)

from .router import router as orchestration_router

__all__ = [
    # Enums
    "Period",
    "DataSource",
    "DataField",
    # Data structures
    "ContextData",
    "HorizonSpec",
    "ForecastData",
    "ContextSummary",
    "InferenceMetadata",
    # Request/Response
    "InferenceRequest",
    "InferenceResponse",
    # Router
    "orchestration_router",
]
