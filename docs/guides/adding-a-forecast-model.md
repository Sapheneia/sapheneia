# Adding a New Forecast Model to Sapheneia

This guide walks through every layer of the system that must be modified when
integrating a new time-series forecasting model. Follow the steps in order;
each step depends on the one before it.

---

## Overview

Sapheneia uses a layered architecture for model integration:

```
Aleutian (Go orchestrator)
    |
    v
orchestration/service.py  (InferenceService.predict)
    |
    +-- determine_model_family()  -> "newmodel"
    +-- get_model_endpoint()      -> "/forecast/v1/newmodel/inference"
    +-- inference_to_newmodel()   -> model-specific request dict
    +-- _run_newmodel_inference() -> HTTP call to model container
    +-- newmodel_to_inference()   -> unified InferenceResponse
    |
    v
forecast/models/newmodel/  (FastAPI container)
    |
    POST /forecast/v1/newmodel/inference
```

The key invariant is that `InferenceRequest` and `InferenceResponse` (defined in
`orchestration/schema.py`) are the only data contracts that cross the
orchestration boundary. Every model-specific format lives behind the adapter
functions.

---

## Step 1: Register the Model Family

**File:** `orchestration/adapters.py`

Two functions must be updated: `determine_model_family()` and
`get_model_endpoint()`.

### 1a. Add family detection

`determine_model_family()` performs a simple substring match on the lowercased
model identifier that Aleutian passes in the request. Add your check before the
final `raise ValueError`.

```python
# orchestration/adapters.py

def determine_model_family(model_name: str) -> str:
    lower_name = model_name.lower()

    if "chronos" in lower_name:
        return "chronos"
    if "timesfm" in lower_name:
        return "timesfm"
    if "moirai" in lower_name:
        return "moirai"
    if "granite" in lower_name:
        return "granite"
    if "moment" in lower_name:
        return "moment"
    if "lag-llama" in lower_name:
        return "lagllama"
    if "yinglong" in lower_name:
        return "yinglong"
    # --- ADD YOUR MODEL FAMILY DETECTION HERE ---
    if "newmodel" in lower_name:
        return "newmodel"

    raise ValueError(f"Unknown model family: {model_name}")
```

The string `"newmodel"` must be a reliable substring of whatever HuggingFace
model ID Aleutian will send (e.g., `"org/newmodel-base"` contains `"newmodel"`).
If the model name is ambiguous, use a more specific prefix.

### 1b. Register the endpoint path

`get_model_endpoint()` maps a family name to the path on the model container.
The path must match the FastAPI route you will define in Step 5.

```python
# orchestration/adapters.py

def get_model_endpoint(model_family: str) -> str:
    endpoints = {
        "chronos": "/forecast/v1/chronos/inference",
        "timesfm": "/forecast/v1/timesfm20/inference",
        "moirai":  "/forecast/v1/moirai/inference",
        "granite": "/forecast/v1/granite/inference",
        "moment":  "/forecast/v1/moment/inference",
        # --- ADD YOUR ENDPOINT HERE ---
        "newmodel": "/forecast/v1/newmodel/inference",
    }

    if model_family not in endpoints:
        raise ValueError(f"No endpoint for model family: {model_family}")

    return endpoints[model_family]
```

---

## Step 2: Create the Request Adapter

**File:** `orchestration/adapters.py`

The request adapter transforms the unified `InferenceRequest` into the
model-specific JSON body that the container endpoint expects.

Reference the `InferenceRequest` fields available to you:

| Field | Type | Description |
|---|---|---|
| `request.context.values` | `List[float]` | Historical data, oldest first |
| `request.context.period` | `Period` | Frequency enum (e.g., `"1d"`) |
| `request.context.start_date` | `str` | ISO date of first context point |
| `request.context.end_date` | `str` | ISO date of last context point |
| `request.context.field` | `DataField` | OHLCV field (usually `close`) |
| `request.horizon.length` | `int` | Number of steps to forecast |
| `request.horizon.period` | `Period` | Forecast frequency |
| `request.params` | `Optional[ModelParams]` | Sampling params (may be `None`) |
| `request.ticker` | `str` | Ticker symbol, for logging only |
| `request.model` | `str` | Full model ID string |
| `request.request_id` | `str` | UUID for tracing |

Add the function after the existing adapter sections, before the legacy adapters:

```python
# orchestration/adapters.py
# Place in a new section: "NEWMODEL ADAPTERS"

def inference_to_newmodel(request: InferenceRequest) -> Dict[str, Any]:
    """
    Transform unified InferenceRequest to NewModel inference format.

    Args:
        request: Unified inference request

    Returns:
        NewModel-compatible request dict for /forecast/v1/newmodel/inference
    """
    params = request.params or {}

    return {
        # Rename fields to match whatever NewModel's API expects.
        # This example assumes NewModel uses "inputs" and "forecast_steps".
        "inputs": request.context.values,
        "forecast_steps": request.horizon.length,
        # Pass through optional sampling parameters when present
        "num_samples": getattr(params, "num_samples", 20),
        "temperature": getattr(params, "temperature", 1.0),
    }
```

Use `getattr(params, "field", default)` rather than `params.field` because
`params` may be `None` when no `ModelParams` block was sent by Aleutian. If
your model requires parameters that do not exist on `ModelParams`, document them
here and accept them from the raw dict; do not add fields to `ModelParams`
unless they are common across multiple models.

---

## Step 3: Create the Response Adapter

**File:** `orchestration/adapters.py`

The response adapter maps the model container's JSON response back to the unified
`InferenceResponse`. It must always populate `forecast`, `context_summary`, and
`metadata`. The `quantiles` field is optional.

```python
# orchestration/adapters.py

def newmodel_to_inference(
    newmodel_response: Dict[str, Any],
    request: InferenceRequest,
    inference_time_ms: int,
) -> InferenceResponse:
    """
    Transform NewModel inference response to unified InferenceResponse.

    Args:
        newmodel_response: Raw JSON response from the NewModel container
        request: The original inference request (used for metadata echo-back)
        inference_time_ms: Wall-clock milliseconds for the HTTP round-trip

    Returns:
        Unified InferenceResponse

    Raises:
        ComputationError: If expected keys are missing from the response
    """
    # --- Extract point forecast ---
    # Adjust the key lookup to match what your container actually returns.
    forecast_values = newmodel_response.get("forecast")
    if not forecast_values:
        raise ComputationError(
            message="NewModel response missing 'forecast' key",
            details={
                "model_family": "newmodel",
                "available_keys": list(newmodel_response.keys()),
            },
        )

    # --- Calculate forecast date range ---
    # calculate_forecast_dates is a helper already in adapters.py.
    # It adds horizon.length * period to context.end_date.
    start_date, end_date = calculate_forecast_dates(
        request.context.end_date,
        request.horizon.length,
        request.horizon.period,
    )

    # --- Optional: map quantiles if the model returns them ---
    quantiles = None
    raw_quantiles = newmodel_response.get("quantiles")  # e.g., {"10": [...], "90": [...]}
    if raw_quantiles:
        from .schema import QuantileForecast
        quantiles = [
            QuantileForecast(quantile=float(q) / 100, values=vals)
            for q, vals in raw_quantiles.items()
        ]

    # --- Build and return unified response ---
    return InferenceResponse(
        request_id=request.request_id,
        ticker=request.ticker,
        model=request.model,
        forecast=ForecastData(
            values=forecast_values,
            period=request.horizon.period,
            start_date=start_date,
            end_date=end_date,
        ),
        context_summary=ContextSummary(
            length=len(request.context.values),
            period=request.context.period,
            source=request.context.source,
            start_date=request.context.start_date,
            end_date=request.context.end_date,
            field=request.context.field,
        ),
        quantiles=quantiles,
        metadata=InferenceMetadata(
            inference_time_ms=inference_time_ms,
            model_version=newmodel_response.get("metadata", {}).get("version", "1.0.0"),
            device=newmodel_response.get("metadata", {}).get("device", "unknown"),
            model_family="newmodel",
        ),
    )
```

**Quantile key format note:** The existing Chronos adapter stores quantile keys
as integer strings (`"10"`, `"50"`, `"90"`). The `QuantileForecast` schema
stores them as floats between 0 and 1. The conversion is `float(q) / 100`.
If your model already returns float keys (e.g., `"0.1"`), use
`float(q)` directly and skip the division.

---

## Step 4: Add Routing in InferenceService

**File:** `orchestration/service.py`

Two changes are required: updating the routing dispatch in `predict()` and
adding a `_run_newmodel_inference()` method.

### 4a. Import the new adapter functions

At the top of the file, extend the existing import from `orchestration.adapters`:

```python
# orchestration/service.py

from .adapters import (
    determine_model_family,
    get_model_endpoint,
    inference_to_chronos,
    chronos_to_inference,
    inference_to_timesfm,
    timesfm_to_inference,
    # --- ADD YOUR IMPORTS ---
    inference_to_newmodel,
    newmodel_to_inference,
    legacy_to_inference,
    inference_to_legacy,
)
```

Also add a URL attribute for your model container in `__init__`:

```python
# orchestration/service.py  InferenceService.__init__

self.chronos_url = os.getenv("CHRONOS_SERVICE_URL", base_url)
self.timesfm_url = os.getenv("TIMESFM_SERVICE_URL", base_url)
# --- ADD YOUR URL ---
self.newmodel_url = os.getenv("NEWMODEL_SERVICE_URL", base_url)
```

### 4b. Add the routing branch in predict()

Find the `if/elif` chain in `predict()` and add a branch before the generic
fallback:

```python
# orchestration/service.py  InferenceService.predict()

if model_family == "chronos":
    response = await self._run_chronos_inference(request)
elif model_family == "timesfm":
    response = await self._run_timesfm_inference(request)
# --- ADD YOUR BRANCH ---
elif model_family == "newmodel":
    response = await self._run_newmodel_inference(request)
else:
    logger.warning(f"Model family {model_family} using generic handler")
    response = await self._run_chronos_inference(request)
```

### 4c. Implement _run_newmodel_inference()

Model-specific inference methods follow a consistent pattern: transform the
request, make an HTTP POST, handle errors with typed exceptions, and transform
the response. Copy the structure of `_run_chronos_inference()` exactly.

```python
# orchestration/service.py

async def _run_newmodel_inference(self, request: InferenceRequest) -> InferenceResponse:
    """
    Execute NewModel inference via HTTP call to the model container.

    Args:
        request: Unified inference request

    Returns:
        Unified inference response

    Raises:
        ServiceUnavailableError: If the container is unreachable
        ServiceTimeoutError: If the request exceeds self.timeout
        ValidationError: If the container returns a 4xx status
        ModelUnavailableError: If the container returns a 5xx status
    """
    start_time = time.time()

    # Transform request to model-specific format
    newmodel_request = inference_to_newmodel(request)

    # The container always exposes /forecast/v1/inference (no model name in path).
    # This is different from get_model_endpoint(), which returns the full path
    # used by the gateway. Dedicated containers use the generic endpoint.
    endpoint = f"{self.newmodel_url}/forecast/v1/inference"
    logger.info(f"Calling NewModel endpoint: {endpoint}")

    try:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {
                "Content-Type": "application/json",
                "X-Request-ID": request.request_id,
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            logger.debug(f"Request ID {request.request_id} -> NewModel")

            resp = await client.post(
                endpoint,
                json=newmodel_request,
                headers=headers,
            )
            resp.raise_for_status()
            newmodel_data = resp.json()

    except httpx.ConnectError as e:
        raise ServiceUnavailableError(
            message=f"NewModel service unreachable at {endpoint}",
            details={"endpoint": endpoint, "error": str(e)},
        )
    except httpx.ReadTimeout:
        raise ServiceTimeoutError(
            message=f"NewModel inference timed out after {self.timeout}s",
            details={"endpoint": endpoint, "timeout": self.timeout},
        )
    except httpx.HTTPStatusError as e:
        if 400 <= e.response.status_code < 500:
            raise ValidationError(
                message=f"NewModel rejected request: {e.response.status_code}",
                details={"status_code": e.response.status_code, "model": request.model},
            )
        raise ModelUnavailableError(
            message=f"NewModel returned {e.response.status_code}",
            details={"status_code": e.response.status_code, "model": request.model},
        )

    inference_time_ms = int((time.time() - start_time) * 1000)

    return newmodel_to_inference(newmodel_data, request, inference_time_ms)
```

The four exception types (`ServiceUnavailableError`, `ServiceTimeoutError`,
`ValidationError`, `ModelUnavailableError`) are already imported at the top of
`service.py` from `shared.errors`. Do not add new error types unless the
existing ones are genuinely insufficient.

---

## Step 5: Create the Model Container

**File tree to create under** `forecast/models/newmodel/`:

```
forecast/models/newmodel/
    __init__.py
    routes/
        __init__.py
        endpoints.py
    schemas/
        __init__.py
        inference.py
    services/
        __init__.py
        model.py
```

### 5a. `__init__.py`

```python
# forecast/models/newmodel/__init__.py
"""
NewModel Module

<Organization>/<Model> - <one-line description>.
Supports variants: newmodel-base, newmodel-large.
"""

__version__ = "1.0.0"
```

### 5b. `schemas/inference.py`

Define the request and response shapes for the container endpoint. These are
internal to the container and do not need to match `InferenceRequest`.

```python
# forecast/models/newmodel/schemas/inference.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ModelInitInput(BaseModel):
    model_variant: Optional[str] = Field(
        default=None,
        description="Model identifier (e.g., 'org/newmodel-base'). "
                    "Falls back to MODEL_VARIANT env var if not provided."
    )
    device: Optional[str] = Field(
        default="cpu",
        description="Compute device: 'cpu', 'cuda', or 'mps'"
    )


class ModelInitOutput(BaseModel):
    message: str
    model_status: str
    model_info: Optional[Dict[str, Any]] = None


class StatusOutput(BaseModel):
    model_status: str
    details: Optional[str] = None


class InferenceInput(BaseModel):
    """Request body accepted by POST /forecast/v1/newmodel/inference."""
    inputs: List[float] = Field(
        ...,
        description="Historical time series values, oldest first"
    )
    forecast_steps: int = Field(
        ...,
        gt=0,
        description="Number of steps to forecast"
    )
    num_samples: Optional[int] = Field(default=20, gt=0)
    temperature: Optional[float] = Field(default=1.0, gt=0)

    class Config:
        json_schema_extra = {
            "example": {
                "inputs": [100.0, 101.2, 99.8, 102.1],
                "forecast_steps": 10,
                "num_samples": 20
            }
        }


class InferenceOutput(BaseModel):
    """Response body returned by POST /forecast/v1/newmodel/inference."""
    prediction: Dict[str, Any] = Field(
        ...,
        description="Forecast results including at minimum a 'forecast' key"
    )
    execution_metadata: Dict[str, Any] = Field(
        ...,
        description="Timing and model version information"
    )


class ShutdownOutput(BaseModel):
    message: str
```

The `InferenceOutput.prediction` dict must contain at minimum the key your
response adapter reads (e.g., `"forecast"`). Document any additional keys
(`"quantiles"`, `"metadata"`) explicitly so the adapter knows what to expect.

### 5c. `services/model.py`

Follow the stateful module pattern from `forecast/models/chronos/services/model.py`.
Use module-level variables protected by a `threading.Lock` so the container can
run as a single-worker process without race conditions.

```python
# forecast/models/newmodel/services/model.py

import os
import logging
import time
import threading
from typing import Tuple, Optional, Any, List, Dict

logger = logging.getLogger(__name__)


class ModelNotInitializedError(Exception):
    """Raised when inference is attempted before the model is loaded."""


class ModelInitializationError(Exception):
    """Raised when model loading fails."""


# Module-level state (single-worker process assumption)
_model = None
_model_status: str = "uninitialized"
_error_message: Optional[str] = None
_model_variant: Optional[str] = None
_device: str = "cpu"
_model_lock = threading.Lock()


def initialize_model(
    model_variant: Optional[str] = None,
    device: Optional[str] = None,
) -> None:
    """
    Load the model from HuggingFace cache (HF_HOME).

    Args:
        model_variant: HuggingFace model ID. Falls back to MODEL_VARIANT env var.
        device: 'cpu', 'cuda', or 'mps'. Falls back to DEVICE env var.

    Raises:
        ModelInitializationError: If loading fails for any reason.
    """
    global _model, _model_status, _error_message, _model_variant, _device

    with _model_lock:
        if _model_status == "ready":
            logger.warning("Model already initialized")
            return
        if _model_status == "initializing":
            raise ModelInitializationError("Initialization already in progress")
        _model_status = "initializing"
        _error_message = None

    model_variant = model_variant or os.getenv("MODEL_VARIANT")
    if not model_variant:
        raise ValueError(
            "model_variant must be provided or MODEL_VARIANT env var must be set"
        )
    device = device or os.getenv("DEVICE", "cpu")

    logger.info(f"Loading NewModel: {model_variant} on {device}")
    start = time.time()

    try:
        # Replace this block with the actual library call for your model.
        # Example for a HuggingFace AutoModel:
        #
        #   from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        #   tokenizer = AutoTokenizer.from_pretrained(model_variant)
        #   loaded_model = AutoModelForSeq2SeqLM.from_pretrained(model_variant)
        #
        loaded_model = _load_newmodel(model_variant, device)

        with _model_lock:
            _model = loaded_model
            _model_variant = model_variant
            _device = device
            _model_status = "ready"

        logger.info(f"NewModel ready in {time.time() - start:.2f}s")

    except Exception as e:
        with _model_lock:
            _model_status = "error"
            _error_message = str(e)
            _model = None
        logger.error(f"NewModel initialization failed: {e}")
        raise ModelInitializationError(f"Model initialization failed: {e}")


def _load_newmodel(model_variant: str, device: str):
    """
    Internal helper that performs the actual model loading.
    Isolates the library-specific code from state management.
    """
    # TODO: replace with real loading logic
    raise NotImplementedError(
        "Replace _load_newmodel() with the library call for your model."
    )


def get_status() -> Tuple[str, Optional[str]]:
    with _model_lock:
        return _model_status, _error_message


def get_model_info() -> Optional[Dict[str, Any]]:
    with _model_lock:
        if _model is None:
            return None
        return {"model_variant": _model_variant, "device": _device, "status": _model_status}


def run_inference(
    inputs: List[float],
    forecast_steps: int,
    num_samples: int = 20,
    temperature: float = 1.0,
) -> Dict[str, Any]:
    """
    Run inference and return a dict compatible with the response adapter.

    The returned dict must contain at minimum:
        "forecast": List[float]   -- point forecast, length == forecast_steps

    Optional keys that the adapter will consume if present:
        "quantiles": Dict[str, List[float]]  -- e.g., {"10": [...], "90": [...]}
        "metadata":  Dict[str, Any]          -- e.g., {"device": "cpu", "version": "1.0"}

    Raises:
        ModelNotInitializedError: If the model is not loaded.
    """
    global _model, _model_status

    with _model_lock:
        if _model_status != "ready" or _model is None:
            raise ModelNotInitializedError(
                f"Model not initialized. Status: {_model_status}"
            )
        model_ref = _model

    logger.info(f"NewModel inference: {len(inputs)} context points, {forecast_steps} steps")
    start = time.time()

    try:
        # TODO: replace with real inference logic using model_ref
        forecast_values = _call_model(model_ref, inputs, forecast_steps, num_samples, temperature)
        elapsed = time.time() - start

        return {
            "forecast": forecast_values,
            "metadata": {
                "context_length": len(inputs),
                "forecast_steps": forecast_steps,
                "model_variant": _model_variant,
                "device": _device,
                "version": "1.0.0",
                "inference_time_seconds": round(elapsed, 3),
            },
        }

    except Exception as e:
        logger.error(f"NewModel inference failed: {e}")
        raise


def _call_model(model_ref, inputs, forecast_steps, num_samples, temperature):
    """
    Internal helper that calls the model and returns List[float].
    Isolates the library-specific code.
    """
    # TODO: implement
    raise NotImplementedError("Replace _call_model() with real inference logic.")


def shutdown_model() -> bool:
    global _model, _model_status, _error_message, _model_variant, _device

    with _model_lock:
        if _model is None:
            logger.warning("Model was not initialized")
            return False
        logger.info(f"Shutting down NewModel ({_model_variant})")
        _model = None
        _model_status = "uninitialized"
        _error_message = None
        _model_variant = None
        _device = "cpu"

    logger.info("NewModel shut down successfully")
    return True
```

### 5d. `routes/endpoints.py`

```python
# forecast/models/newmodel/routes/endpoints.py

from fastapi import APIRouter, HTTPException, Depends, Request, Response, Body
import logging
import time

from ..schemas.inference import (
    ModelInitInput, ModelInitOutput,
    InferenceInput, InferenceOutput,
    ShutdownOutput, StatusOutput,
)
from ..services import model as newmodel_service
from ....core.security import get_api_key
from ....core.rate_limit import limiter, get_rate_limit
from ....core.exceptions import (
    ModelNotInitializedError,
    ModelInitializationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/newmodel",
    tags=["NewModel"],
    dependencies=[Depends(get_api_key)],
)


@router.post("/initialization", response_model=ModelInitOutput)
@limiter.limit(get_rate_limit("initialization"))
async def initialize_model_endpoint(
    request: Request,
    response: Response,
    init_input: ModelInitInput = Body(),
):
    """Initialize the NewModel. Call this before the first /inference request."""
    status, _ = newmodel_service.get_status()

    if status == "ready":
        return ModelInitOutput(
            message="Model already initialized",
            model_status="ready",
            model_info=newmodel_service.get_model_info(),
        )
    if status == "initializing":
        raise HTTPException(status_code=409, detail="Initialization already in progress")

    try:
        newmodel_service.initialize_model(
            model_variant=init_input.model_variant,
            device=init_input.device,
        )
        return ModelInitOutput(
            message="Model initialized successfully",
            model_status="ready",
            model_info=newmodel_service.get_model_info(),
        )
    except ModelInitializationError as e:
        raise ModelInitializationError(str(e))
    except ValueError as e:
        from ....core.exceptions import ConfigurationError
        raise ConfigurationError(str(e), setting="model_variant")


@router.get("/status", response_model=StatusOutput)
@limiter.limit(get_rate_limit("default"))
async def get_model_status(request: Request, response: Response):
    """Return the current model status."""
    status, error_msg = newmodel_service.get_status()
    model_info = newmodel_service.get_model_info()
    details = f"Model: {model_info.get('model_variant')}" if model_info else None
    if error_msg:
        details = f"{details}. Error: {error_msg}" if details else f"Error: {error_msg}"
    return StatusOutput(model_status=status, details=details)


@router.post("/inference", response_model=InferenceOutput)
@limiter.limit(get_rate_limit("inference"))
async def inference_endpoint(
    request: Request,
    response: Response,
    input_data: InferenceInput = Body(),
):
    """
    Run inference on the provided context values.

    The model must be initialized via /initialization before calling this endpoint.
    """
    status, error_msg = newmodel_service.get_status()
    if status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Model not initialized. Status: {status}. "
                   f"Call /initialization first.",
        )

    start_time = time.time()

    try:
        results = newmodel_service.run_inference(
            inputs=input_data.inputs,
            forecast_steps=input_data.forecast_steps,
            num_samples=input_data.num_samples,
            temperature=input_data.temperature,
        )
        total_time = time.time() - start_time

        return InferenceOutput(
            prediction=results,
            execution_metadata={
                "total_time_seconds": round(total_time, 3),
                "model_version": newmodel_service._model_variant,
                "api_version": "1.0.0",
            },
        )

    except (ModelNotInitializedError, newmodel_service.ModelNotInitializedError) as e:
        raise ModelNotInitializedError(str(e))
    except Exception:
        logger.exception("NewModel inference failed")
        raise


@router.post("/shutdown", response_model=ShutdownOutput)
@limiter.limit(get_rate_limit("default"))
async def shutdown_model_endpoint(request: Request, response: Response):
    """Shut down the model and release memory."""
    success = newmodel_service.shutdown_model()
    if success:
        return ShutdownOutput(message="Model shut down successfully")
    return ShutdownOutput(message="Model was not initialized or already shut down")
```

### 5e. Register the router in `forecast/main.py`

```python
# forecast/main.py  (additions only)

from .models.newmodel.routes import endpoints as newmodel_endpoints

# ...existing router includes...
app.include_router(
    newmodel_endpoints.router,
    prefix="/forecast/v1",
)
```

---

## Step 6: Add to docker-compose.yml

Add a new service block. Assign a port number from the 127xx scheme that does
not conflict with any existing service.

```yaml
# docker-compose.yml

  forecast-newmodel-base:
    build:
      context: .
      dockerfile: Dockerfile.forecast
      args:
        MODEL_NAME: newmodel
        MODEL_PORT: 8000
    container_name: forecast-newmodel-base
    ports:
      - "${NEWMODEL_BASE_PORT:-12730}:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_NAME=newmodel
      - MODEL_VARIANT=org/newmodel-base
      - HF_HOME=/models_cache
      - DEVICE=cpu
      - PYTHONPATH=/app
      - API_SECRET_KEY=${API_SECRET_KEY}
    volumes:
      - ./forecast:/app/forecast
      - ./logs:/app/logs
      - ${MODELS_CACHE_PATH:-./models_cache}:/models_cache
    networks:
      - aleutian-network
    restart: "no"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

Add a `volumes` entry if your model caches data to a named volume (see how
`forecast_models_timesfm20` is declared in the existing `volumes:` section at
the bottom of the file).

Add the corresponding environment variable to `.env.template`:

```
# NewModel service port
NEWMODEL_BASE_PORT=12730
NEWMODEL_SERVICE_URL=http://forecast-newmodel-base:8000
```

Also update `InferenceService.__init__` in `orchestration/service.py` to read
`NEWMODEL_SERVICE_URL` (as shown in Step 4a).

---

## Step 7: Create Strategy YAML Files

Strategy YAML files drive backtests via the simulation engine. Create one file
per ticker per model variant. The convention is
`simulations/strategies/{TICKER}/{ticker_lowercase}_{model_slug}.yaml`.

```yaml
# simulations/strategies/SPY/spy_newmodel_base.yaml

metadata:
  id: "spy-newmodel-base"
  version: "1.0.0"
  description: "SPY backtest using NewModel Base"
  author: "Sapheneia"

evaluation:
  ticker: "SPY"
  fetch_start_date: "20211201"
  start_date: "20230101"
  end_date: "20240101"

forecast:
  model: "org/newmodel-base"
  context_size: 252
  horizon_size: 20

trading:
  initial_capital: 100000.0
  initial_position: 0.0
  initial_cash: 100000.0
  strategy_type: "threshold"
  params:
    threshold_type: "absolute"
    threshold_value: 2.0
    execution_size: 10.0
```

Key fields to verify:

- `forecast.model` must match the string that `determine_model_family()` can
  classify. The substring `"newmodel"` must appear in `"org/newmodel-base"`.
- `forecast.context_size` must be a value the model supports. Check the model
  documentation for minimum context length requirements.
- `forecast.horizon_size` must be within the `HorizonSpec.length` maximum of
  365 (enforced by the Pydantic schema in `orchestration/schema.py`).

Replicate the file for every ticker in `simulations/strategies/` that you want
to backtest. The existing codebase has files under at least `SPY/`, `QQQ/`, and
`IWM/` subdirectories.

---

## Step 8: Write Tests

Create a test file at `tests/forecast/test_newmodel_adapters.py` (unit tests)
and extend `tests/forecast/test_endpoints.py` with a new class for the container
endpoint.

### 8a. Adapter unit tests

These tests require no running containers and no real model weights. They verify
that your pure transformation functions behave correctly.

```python
# tests/forecast/test_newmodel_adapters.py

import pytest
from orchestration.schema import (
    InferenceRequest,
    ContextData,
    HorizonSpec,
    Period,
    DataSource,
    DataField,
)
from orchestration.adapters import (
    determine_model_family,
    get_model_endpoint,
    inference_to_newmodel,
    newmodel_to_inference,
)
from shared.errors import ComputationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_request():
    return InferenceRequest(
        ticker="SPY",
        model="org/newmodel-base",
        context=ContextData(
            values=[100.0, 101.0, 102.0, 103.0, 104.0],
            period=Period.DAY_1,
            source=DataSource.YAHOO,
            start_date="2025-01-01",
            end_date="2025-01-05",
            field=DataField.CLOSE,
        ),
        horizon=HorizonSpec(length=3, period=Period.DAY_1),
    )


# ---------------------------------------------------------------------------
# Family detection
# ---------------------------------------------------------------------------

class TestDetermineModelFamily:
    def test_detects_newmodel_lowercase(self):
        assert determine_model_family("org/newmodel-base") == "newmodel"

    def test_detects_newmodel_mixed_case(self):
        assert determine_model_family("Org/NewModel-Large") == "newmodel"

    def test_existing_families_unaffected(self):
        assert determine_model_family("amazon/chronos-t5-tiny") == "chronos"
        assert determine_model_family("google/timesfm-2.0-500m-pytorch") == "timesfm"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown model family"):
            determine_model_family("unknown/mystery-model")


# ---------------------------------------------------------------------------
# Endpoint lookup
# ---------------------------------------------------------------------------

class TestGetModelEndpoint:
    def test_newmodel_endpoint(self):
        assert get_model_endpoint("newmodel") == "/forecast/v1/newmodel/inference"

    def test_unknown_family_raises(self):
        with pytest.raises(ValueError, match="No endpoint for model family"):
            get_model_endpoint("nonexistent")


# ---------------------------------------------------------------------------
# Request adapter
# ---------------------------------------------------------------------------

class TestInferenceToNewmodel:
    def test_maps_context_values(self, sample_request):
        result = inference_to_newmodel(sample_request)
        assert result["inputs"] == sample_request.context.values

    def test_maps_horizon_length(self, sample_request):
        result = inference_to_newmodel(sample_request)
        assert result["forecast_steps"] == sample_request.horizon.length

    def test_default_sampling_params(self, sample_request):
        result = inference_to_newmodel(sample_request)
        assert result["num_samples"] == 20
        assert result["temperature"] == 1.0

    def test_custom_sampling_params(self, sample_request):
        from orchestration.schema import ModelParams
        sample_request.params = ModelParams(num_samples=50, temperature=0.8)
        result = inference_to_newmodel(sample_request)
        assert result["num_samples"] == 50
        assert result["temperature"] == 0.8


# ---------------------------------------------------------------------------
# Response adapter
# ---------------------------------------------------------------------------

class TestNewmodelToInference:
    def _make_response(self, forecast_values=None):
        return {
            "forecast": forecast_values or [105.0, 106.0, 107.0],
            "metadata": {"device": "cpu", "version": "1.0.0"},
        }

    def test_point_forecast_values(self, sample_request):
        raw = self._make_response([105.0, 106.0, 107.0])
        result = newmodel_to_inference(raw, sample_request, 123)
        assert result.forecast.values == [105.0, 106.0, 107.0]

    def test_forecast_dates_calculated(self, sample_request):
        raw = self._make_response()
        result = newmodel_to_inference(raw, sample_request, 123)
        assert result.forecast.start_date == "2025-01-06"
        assert result.forecast.end_date == "2025-01-08"

    def test_context_summary_echoed(self, sample_request):
        raw = self._make_response()
        result = newmodel_to_inference(raw, sample_request, 123)
        assert result.context_summary.length == 5
        assert result.context_summary.source == DataSource.YAHOO

    def test_metadata_populated(self, sample_request):
        raw = self._make_response()
        result = newmodel_to_inference(raw, sample_request, 250)
        assert result.metadata.inference_time_ms == 250
        assert result.metadata.model_family == "newmodel"
        assert result.metadata.device == "cpu"

    def test_missing_forecast_key_raises(self, sample_request):
        raw = {"quantiles": {}}  # missing "forecast"
        with pytest.raises(ComputationError):
            newmodel_to_inference(raw, sample_request, 100)

    def test_quantiles_mapped_when_present(self, sample_request):
        raw = self._make_response()
        raw["quantiles"] = {"10": [104.0, 105.0, 106.0], "90": [106.0, 107.0, 108.0]}
        result = newmodel_to_inference(raw, sample_request, 100)
        assert result.quantiles is not None
        assert len(result.quantiles) == 2
        quantile_levels = {q.quantile for q in result.quantiles}
        assert 0.1 in quantile_levels
        assert 0.9 in quantile_levels

    def test_no_quantiles_when_absent(self, sample_request):
        raw = self._make_response()
        result = newmodel_to_inference(raw, sample_request, 100)
        assert result.quantiles is None

    def test_request_id_preserved(self, sample_request):
        raw = self._make_response()
        result = newmodel_to_inference(raw, sample_request, 100)
        assert result.request_id == sample_request.request_id
```

### 8b. Service routing test

```python
# tests/forecast/test_newmodel_service_routing.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from orchestration.service import InferenceService
from orchestration.schema import (
    InferenceRequest, ContextData, HorizonSpec, Period, DataSource, DataField
)


@pytest.fixture
def service():
    return InferenceService(base_url="http://localhost:8000")


@pytest.fixture
def newmodel_request():
    return InferenceRequest(
        ticker="SPY",
        model="org/newmodel-base",
        context=ContextData(
            values=[100.0] * 10,
            period=Period.DAY_1,
            source=DataSource.YAHOO,
            start_date="2025-01-01",
            end_date="2025-01-10",
            field=DataField.CLOSE,
        ),
        horizon=HorizonSpec(length=5, period=Period.DAY_1),
    )


@pytest.mark.asyncio
async def test_predict_routes_to_newmodel(service, newmodel_request):
    """predict() must call _run_newmodel_inference for newmodel family."""
    mock_response = MagicMock()

    with patch.object(
        service,
        "_run_newmodel_inference",
        new=AsyncMock(return_value=mock_response),
    ) as mock_method:
        result = await service.predict(newmodel_request)

    mock_method.assert_called_once_with(newmodel_request)
    assert result is mock_response
```

### 8c. Container endpoint test

Add a new class to `tests/forecast/test_endpoints.py` following the existing
`TestAuthentication` and `TestInputValidation` pattern:

```python
# tests/forecast/test_endpoints.py  (additions only)

class TestNewModelEndpoint:
    """Tests for the NewModel container endpoint."""

    def test_status_requires_auth(self, client):
        response = client.get("/forecast/v1/newmodel/status")
        assert response.status_code in [401, 403]

    def test_status_with_auth_returns_structure(self, client, auth_headers):
        response = client.get("/forecast/v1/newmodel/status", headers=auth_headers)
        assert response.status_code == 200
        assert "model_status" in response.json()

    def test_inference_requires_auth(self, client):
        payload = {"inputs": [1.0, 2.0, 3.0], "forecast_steps": 5}
        response = client.post("/forecast/v1/newmodel/inference", json=payload)
        assert response.status_code in [401, 403]

    def test_inference_rejects_missing_inputs(self, client, auth_headers):
        payload = {"forecast_steps": 5}
        response = client.post(
            "/forecast/v1/newmodel/inference",
            headers=auth_headers,
            json=payload,
        )
        assert response.status_code == 422

    def test_inference_rejects_zero_forecast_steps(self, client, auth_headers):
        payload = {"inputs": [1.0, 2.0, 3.0], "forecast_steps": 0}
        response = client.post(
            "/forecast/v1/newmodel/inference",
            headers=auth_headers,
            json=payload,
        )
        assert response.status_code == 422

    def test_inference_returns_409_before_initialization(self, client, auth_headers):
        payload = {"inputs": [1.0, 2.0, 3.0], "forecast_steps": 5}
        response = client.post(
            "/forecast/v1/newmodel/inference",
            headers=auth_headers,
            json=payload,
        )
        # Model is not initialized in test environment
        assert response.status_code == 409
```

Run all adapter tests without any model weights or running containers:

```
pytest tests/forecast/test_newmodel_adapters.py -v
pytest tests/forecast/test_newmodel_service_routing.py -v
```

Run the endpoint tests against the full FastAPI app:

```
pytest tests/forecast/test_endpoints.py::TestNewModelEndpoint -v
```

---

## Checklist

Use this checklist before opening a pull request:

- [ ] `determine_model_family()` returns the correct family for all expected model ID strings
- [ ] `get_model_endpoint()` returns the path that matches the FastAPI route prefix
- [ ] `inference_to_newmodel()` produces a dict that the container schema accepts without validation errors
- [ ] `newmodel_to_inference()` raises `ComputationError` when required keys are missing
- [ ] `_run_newmodel_inference()` covers `ConnectError`, `ReadTimeout`, 4xx, and 5xx cases
- [ ] The FastAPI router prefix in `routes/endpoints.py` matches the path in `get_model_endpoint()`
- [ ] The `InferenceOutput.prediction` dict always contains at least the `"forecast"` key
- [ ] The docker-compose port does not conflict with any existing service
- [ ] `NEWMODEL_SERVICE_URL` is documented in `.env.template`
- [ ] Strategy YAML `forecast.model` value passes `determine_model_family()` without raising
- [ ] All adapter unit tests pass with `pytest tests/forecast/test_newmodel_adapters.py`
- [ ] All endpoint tests pass with `pytest tests/forecast/test_endpoints.py::TestNewModelEndpoint`
