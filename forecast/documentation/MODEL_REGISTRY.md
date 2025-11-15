# Forecast Application - Model Registry Guide

Complete guide to the model registry system and adding new models to the Forecast Application.

## Table of Contents

1. [Overview](#overview)
2. [Current Models](#current-models)
3. [Planned Models](#planned-models)
4. [Model Registry Structure](#model-registry-structure)
5. [Adding a New Model](#adding-a-new-model)
6. [Model Module Structure](#model-module-structure)
7. [Model Service Requirements](#model-service-requirements)
8. [Testing New Models](#testing-new-models)
9. [Deployment Considerations](#deployment-considerations)

## Overview

The model registry (`forecast/models/__init__.py`) provides centralized model discovery and management. It enables:

- **Model Discovery**: List all available models via `/models` endpoint
- **Dynamic Routing**: Automatically include model routers in the FastAPI app
- **Metadata Management**: Store model information (name, version, description, etc.)
- **Status Tracking**: Track model status (active, planned, deprecated)

## Current Models

### TimesFM-2.0

- **ID**: `timesfm20`
- **Name**: TimesFM 2.0
- **Version**: 2.0.500m
- **Description**: Google's TimesFM 2.0 - 500M parameter foundation model for time series forecasting
- **Status**: `active`
- **Default Port**: 8001 (for separate service deployment)
- **Base Path**: `/forecast/v1/timesfm20/`

**Documentation**: [TimesFM-2.0 Documentation](../models/timesfm20/documentation/)

## Planned Models

### Chronos

- **ID**: `chronos`
- **Name**: Chronos
- **Version**: 1.0
- **Description**: Amazon's Chronos - Transformer-based forecasting model
- **Status**: `planned`
- **Default Port**: 8002

### Prophet

- **ID**: `prophet`
- **Name**: Prophet
- **Version**: Latest
- **Description**: Meta's Prophet - Additive time series forecasting model
- **Status**: `planned`
- **Default Port**: 8003

## Model Registry Structure

### Registry Dictionary

The model registry is a dictionary mapping model IDs to configuration:

```python
MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "model_id": {
        "name": "Model Display Name",
        "version": "Model Version",
        "description": "Model description",
        "module": "forecast.models.model_id",
        "router_path": "forecast.models.model_id.routes.endpoints",
        "service_path": "forecast.models.model_id.services.model",
        "default_port": 8001,
        "status": "active"  # or "planned", "deprecated"
    }
}
```

### Registry Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | ✅ | Human-readable model name |
| `version` | str | ✅ | Model version string |
| `description` | str | ✅ | Model description |
| `module` | str | ✅ | Python module path |
| `router_path` | str | ✅ | Path to router module |
| `service_path` | str | ✅ | Path to service module |
| `default_port` | int | ✅ | Default port for separate service |
| `status` | str | ✅ | Model status (active/planned/deprecated) |

### Registry Functions

**`get_available_models()`**
- Returns list of active model IDs
- Used by `/models` endpoint

**`get_model_info(model_id)`**
- Returns metadata for specific model
- Raises `KeyError` if model not found

**`get_all_models_info()`**
- Returns complete registry
- Used by `/models` endpoint

## Adding a New Model

### Step-by-Step Guide

**Example: Adding Chronos**

#### Step 1: Create Model Directory Structure

```bash
mkdir -p forecast/models/chronos/{routes,schemas,services,local,documentation,tests}
```

#### Step 2: Create Model Module Files

**`forecast/models/chronos/__init__.py`**
```python
"""Chronos model module."""
```

**`forecast/models/chronos/routes/__init__.py`**
```python
"""Chronos API routes."""
```

**`forecast/models/chronos/routes/endpoints.py`**
```python
from fastapi import APIRouter, Depends
from ....core.security import get_api_key

router = APIRouter(
    prefix="/chronos",
    tags=["Chronos"],
    dependencies=[Depends(get_api_key)]
)

@router.get("/status")
async def get_status():
    """Check Chronos model status."""
    return {"status": "ready"}
```

**`forecast/models/chronos/schemas/__init__.py`**
```python
"""Chronos Pydantic schemas."""
```

**`forecast/models/chronos/schemas/schema.py`**
```python
from pydantic import BaseModel

class ChronosInitInput(BaseModel):
    """Chronos initialization input."""
    pass

class ChronosInferenceInput(BaseModel):
    """Chronos inference input."""
    pass
```

**`forecast/models/chronos/services/__init__.py`**
```python
"""Chronos services."""
```

**`forecast/models/chronos/services/model.py`**
```python
"""Chronos model service."""
def get_status():
    """Get model status."""
    return "ready", None
```

#### Step 3: Register in Model Registry

**`forecast/models/__init__.py`**
```python
MODEL_REGISTRY = {
    "timesfm20": {
        # ... existing ...
    },
    "chronos": {
        "name": "Chronos",
        "version": "1.0",
        "description": "Amazon Chronos forecasting model",
        "module": "forecast.models.chronos",
        "router_path": "forecast.models.chronos.routes.endpoints",
        "service_path": "forecast.models.chronos.services.model",
        "default_port": 8002,
        "status": "active"
    }
}
```

#### Step 4: Import Router in main.py

**`forecast/main.py`**
```python
# Import routers from model modules
from .models.timesfm20.routes import endpoints as timesfm20_endpoints
from .models.chronos.routes import endpoints as chronos_endpoints  # NEW

# Include routers
app.include_router(
    timesfm20_endpoints.router,
    prefix="/forecast/v1"
)
app.include_router(
    chronos_endpoints.router,
    prefix="/forecast/v1"
)
```

#### Step 5: Update Dockerfile (Optional)

**`Dockerfile.forecast`**
```dockerfile
# Install Chronos dependencies
RUN if [ "$MODEL_NAME" = "chronos" ] || [ "$MODEL_NAME" = "all" ]; then \
        uv pip install --system chronos-forecasting; \
    fi
```

#### Step 6: Test

```bash
# List models
curl http://localhost:8000/models
# Should show both timesfm20 and chronos

# Test Chronos endpoint
curl http://localhost:8000/forecast/v1/chronos/status \
  -H "Authorization: Bearer YOUR_KEY"
```

## Model Module Structure

Each model module should follow this structure:

```
forecast/models/{model_id}/
├── __init__.py
├── routes/
│   ├── __init__.py
│   └── endpoints.py          # API endpoints
├── schemas/
│   ├── __init__.py
│   └── schema.py             # Pydantic schemas
├── services/
│   ├── __init__.py
│   ├── model.py              # Model service
│   └── data.py               # Data service (optional)
├── local/                     # Local model artifacts
├── tests/                     # Model-specific tests
└── documentation/             # Model-specific documentation
    ├── ARCHITECTURE.md
    ├── API_REFERENCE.md
    ├── DATA_FORMAT.md
    ├── PARAMETERS.md
    ├── USAGE_GUIDE.md
    └── EXAMPLES.md
```

### Directory Descriptions

**`routes/endpoints.py`**
- Defines FastAPI router with model-specific endpoints
- Applies authentication and rate limiting
- Handles request/response formatting

**`schemas/schema.py`**
- Pydantic models for request/response validation
- Input/output schemas for all endpoints

**`services/model.py`**
- Model initialization and state management
- Inference execution
- Status tracking

**`services/data.py`** (Optional)
- Model-specific data loading and transformation
- Data validation
- Covariates preparation

**`local/`**
- Local model artifacts (checkpoints, weights)
- Model cache directory

**`tests/`**
- Model-specific unit and integration tests

**`documentation/`**
- Model-specific documentation (see model-level documentation structure)

## Model Service Requirements

Each model service (`services/model.py`) must implement:

### Required Functions

**`initialize_model(...)`**
- Initialize model from source (HuggingFace, local, MLflow)
- Update model state
- Return initialization status

**`get_status()`**
- Return tuple: `(status: str, error_message: Optional[str])`
- Status values: `"uninitialized"`, `"initializing"`, `"ready"`, `"error"`

**`get_model_config()`**
- Return model configuration dictionary
- Include: backend, context_len, horizon_len, source, etc.

**`get_model_source_info()`**
- Return model source information string
- Format: `"hf:google/model-id"` or `"local:path/to/model"`

**`shutdown_model()`**
- Clean up model resources
- Reset model state to `"uninitialized"`

### Optional Functions

**`run_inference(...)`** (if applicable)
- Execute model inference
- Return forecast results

### State Management

Model services should use module-level state with thread locks:

```python
import threading
from typing import Optional

_model_instance: Optional[Model] = None
_model_status: str = "uninitialized"
_model_lock = threading.Lock()

def initialize_model(...):
    with _model_lock:
        global _model_instance, _model_status
        _model_status = "initializing"
        try:
            _model_instance = load_model(...)
            _model_status = "ready"
        except Exception as e:
            _model_status = "error"
            raise
```

## Testing New Models

### Unit Tests

Create tests in `forecast/models/{model_id}/tests/`:

```python
# test_model_service.py
import pytest
from ..services.model import initialize_model, get_status

def test_model_initialization():
    initialize_model(backend="cpu")
    status, error = get_status()
    assert status == "ready"
```

### Integration Tests

Test API endpoints:

```python
# test_endpoints.py
import pytest
from fastapi.testclient import TestClient
from forecast.main import app

client = TestClient(app)

def test_chronos_status():
    response = client.get(
        "/forecast/v1/chronos/status",
        headers={"Authorization": "Bearer test_key"}
    )
    assert response.status_code == 200
```

### Manual Testing

1. **Start API:**
```bash
./setup.sh run-venv forecast api
```

2. **List Models:**
```bash
curl http://localhost:8000/models
```

3. **Test Endpoints:**
```bash
curl http://localhost:8000/forecast/v1/chronos/status \
  -H "Authorization: Bearer YOUR_KEY"
```

## Deployment Considerations

### Single API Gateway (Default)

All models accessible via single API:
- Base URL: `http://localhost:8000`
- Endpoints: `/forecast/v1/{model_id}/*`
- Easiest for orchestrators and load balancers

### Separate Model Services (Optional)

Each model runs in its own container:
- Configure in `docker-compose.yml`
- Each model on dedicated port
- Enables independent scaling

### Docker Compose Configuration

```yaml
# Separate Chronos service
forecast-chronos:
  build:
    context: .
    dockerfile: Dockerfile.forecast
    args:
      MODEL_NAME: chronos
      MODEL_PORT: 8002
  container_name: sapheneia-forecast-chronos
  ports:
    - "8002:8002"
  # ... rest of config
```

### Resource Requirements

Consider model-specific resource requirements:
- **Memory**: Model size and batch processing needs
- **CPU**: Inference speed requirements
- **GPU**: Optional for faster inference
- **Disk**: Model weights and cache storage

### State Management

⚠️ **Current Limitation**: Module-level state requires single worker per model.

For production scaling:
- Implement Redis state backend
- Enable multiple workers
- Enable horizontal scaling

---

**See also:**
- [Architecture Documentation](ARCHITECTURE.md) - System architecture
- [Deployment Guide](DEPLOYMENT.md) - Deployment instructions
- [TimesFM-2.0 Documentation](../models/timesfm20/documentation/) - Example model documentation

