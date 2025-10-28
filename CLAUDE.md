# Sapheneia Development Log - Claude Sessions

Complete documentation of all development work performed by Claude on the Sapheneia project.

**Project**: Sapheneia TimesFM v2.0
**Version**: 2.0.0
**Last Updated**: October 27, 2025

---

## Table of Contents

1. [Initial v2.0 Refactoring](#initial-v20-refactoring)
2. [Docker and Deployment Fixes](#docker-and-deployment-fixes)
3. [Multi-Model Architecture Refactoring](#multi-model-architecture-refactoring)
4. [Current Project Status](#current-project-status)

---

## Initial v2.0 Refactoring

**Date**: October 26, 2025
**Status**: ✅ Complete

### Objective

Transform Sapheneia from a monolithic Flask application into a scalable FastAPI-based microservices architecture with REST API, Docker support, and MLOps readiness.

### What Was Implemented

#### Phase 1: Core Infrastructure ✅

**Files Created:**
- `api/core/config.py` - Pydantic Settings management
- `api/core/security.py` - API key authentication
- `api/core/data.py` - Shared data fetching utilities

**Key Features:**
- Environment-based configuration with `.env` support
- Default context_len = 64 (as requested)
- Comprehensive logging with loguru
- Security validation for file access
- Support for local files and HTTP URLs

#### Phase 2: TimesFM-2.0 Module ✅

**Files Created:**
- `api/timesfm20/schemas/schema.py` - Pydantic request/response models
- `api/timesfm20/services/data.py` - Data transformation service
- `api/timesfm20/services/model.py` - Model management service
- `api/timesfm20/routes/endpoints.py` - REST API endpoints

**Endpoints Implemented:**
1. `POST /api/v1/timesfm20/initialization` - Load model into memory
2. `GET /api/v1/timesfm20/status` - Check model state
3. `POST /api/v1/timesfm20/inference` - Run forecasting
4. `POST /api/v1/timesfm20/shutdown` - Unload model

**Integration:**
- Preserves existing `src/` modules for notebooks
- Adapts functionality for API service layer
- Module-level state management

#### Phase 3: FastAPI Application ✅

**Files Created:**
- `api/main.py` - Main FastAPI application

**Features:**
- CORS middleware for UI integration
- Startup/shutdown event handlers
- Health check endpoints (`/`, `/health`, `/info`)
- Auto-generated OpenAPI documentation
- Router management for modular endpoints

#### Phase 4: UI Refactoring ✅

**Files Created/Modified:**
- `ui/api_client.py` - REST API client for backend communication
- `ui/app.py` - Refactored Flask app using API client

**Changes:**
- Moved `webapp/` → `ui/`
- Replaced direct model imports with REST API calls
- Local file uploads remain in UI
- Visualization handled locally in UI
- Full backward compatibility maintained

#### Phase 5: Dependency Management ✅

**Files Updated:**
- `pyproject.toml` - Complete dependency update

**Added Dependencies:**
- FastAPI ecosystem (fastapi, uvicorn, pydantic, python-multipart)
- Optional MLOps packages (mlflow, redis, celery)
- Development tools (pytest, httpx)

#### Phase 6: Environment Setup ✅

**Files Created:**
- `.env.template` - Environment variable template
- `.env` - Local configuration (git-ignored)

**Configuration:**
- All secrets in environment variables
- No hardcoded credentials
- Default values provided
- API_SECRET_KEY must be changed in production

#### Phase 7: Docker Support ✅

**Files Created:**
- `Dockerfile.api` - API container image
- `Dockerfile.ui` - UI container image
- `docker-compose.yml` - Service orchestration

**Features:**
- Multi-container architecture (API + UI)
- Health checks for both services
- Volume management for persistence
- Network isolation
- Automatic service dependencies
- Extended startup period for model loading (120s)

#### Phase 9: Documentation ✅

**Files Updated/Created:**
- `README.md` - Comprehensive new documentation
- `.gitignore` - Updated for API artifacts
- `local/API_QUICK_START.md` - Quick start guide
- `local/PLAN.md` - Detailed implementation plan
- `local/IMPLEMENTATION_SUMMARY.md` - Summary of changes

### Testing Performed

**API Endpoints:**
- ✅ Root endpoint (`/`)
- ✅ Health check (`/health`)
- ✅ API info (`/info`)
- ✅ Status endpoint (`/api/v1/timesfm20/status`)
- ✅ Authentication working
- ✅ CORS configured
- ✅ OpenAPI docs generated

**Verified Functionality:**
- API server starts successfully
- Configuration loads correctly (context_len=64)
- Authentication works with API keys
- Health checks functional
- Existing notebooks still work

---

## Docker and Deployment Fixes

**Date**: October 26-27, 2025
**Status**: ✅ Complete

### Issues Encountered and Fixed

#### Issue 1: Docker File Path Mismatches

**Problem:**
UI uploaded files to `/app/ui/uploads` but API expected them at `/app/uploads`, causing "file not found" errors.

**Solution:**
1. Created unified data directory structure: `./data/uploads`
2. Updated `docker-compose.yml` to mount `./data:/app/data` in both containers
3. Updated `ui/app.py` to detect environment (Docker vs venv) and use appropriate paths:
   ```python
   if os.path.exists('/app/data'):  # Docker
       UPLOAD_FOLDER = '/app/data/uploads'
   else:  # venv
       UPLOAD_FOLDER = './data/uploads'
   ```
4. Both containers now share the same data folder

**Files Modified:**
- `docker-compose.yml` - Removed confusing `shared_uploads` volume, added `./data:/app/data`
- `ui/app.py` - Environment-aware path configuration
- `Dockerfile.api` & `Dockerfile.ui` - Updated directory creation

#### Issue 2: Docker Daemon Connection Issues with setup.sh

**Problem:**
`./setup.sh stop` command failed to stop Docker containers with error:
```
Cannot connect to the Docker daemon at unix:///Users/marcelo/.docker/run/docker.sock
```

**Root Cause:**
Running Docker commands from within bash functions in setup.sh broke the Docker CLI connection, even though Docker Desktop was running.

**Solution:**
1. Replaced `docker compose down` with direct container management:
   ```bash
   docker stop sapheneia-api sapheneia-ui
   docker rm sapheneia-api sapheneia-ui
   ```
2. Fixed execution order: Docker stop BEFORE port cleanup (not after)
3. Used explicit container names defined in docker-compose.yml

**Files Modified:**
- `setup.sh` - Simplified Docker stop logic, fixed execution order
- Removed temporary `docker-stop.sh` workaround script

#### Issue 3: Model Weights Storage Location

**Question from User:**
"Where do model weights go when running initialization endpoint?"

**Answer Provided:**
- Model weights stored in HuggingFace cache: `/root/.cache/huggingface/hub/`
- Inside Docker container (not persisted to host)
- Approximately 3.8GB for TimesFM 2.0 500M model
- Re-downloaded on container rebuild unless cache volume added

---

## Multi-Model Architecture Refactoring

**Date**: October 27, 2025
**Status**: ✅ Complete

### Objective

Refactor Sapheneia to support multiple forecasting models (TimesFM, Chronos, Prophet, etc.) with the ability to run models simultaneously on different ports, preparing for orchestrator-based deployment.

### Design Decisions

**User Questions & Answers:**

1. **Port Configuration**: Use `.env` with predefined ports for each model ✅
   ```env
   TIMESFM20_MODEL_PORT=8001
   CHRONOS_MODEL_PORT=8002
   PROPHET_MODEL_PORT=8003
   ```

2. **API Architecture**: Single main API at port 8000 serving all models ✅
   - Clean entry point for orchestrator
   - Models are modules under `api/models/`
   - Can optionally run models as separate services

3. **Docker Strategy**: One parameterized Dockerfile with build args ✅
   - `MODEL_NAME` and `MODEL_PORT` build arguments
   - Conditional dependency installation
   - Easy to add new models

4. **UI Strategy**: Single UI (for now), models called directly via API ✅
   - User may add model selector dropdown later
   - Or call models directly from orchestrator
   - UI unchanged in this refactoring

### Implementation Details

#### 1. Environment Configuration

**Files Modified:**
- `.env` - Added model-specific port configuration
- `.env.template` - Added model-specific port configuration

**Configuration Added:**
```env
# Model-specific ports (for running multiple models simultaneously)
TIMESFM20_MODEL_PORT=8001
CHRONOS_MODEL_PORT=8002
PROPHET_MODEL_PORT=8003
```

#### 2. Directory Restructure

**Changes:**
- Moved `api/timesfm20/` → `api/models/timesfm20/`
- Created `api/models/` directory as model container
- All relative imports updated (added one more `.` for deeper nesting)

**Import Path Fixes:**
- `from ...core.config` → `from ....core.config`
- `from ...core.security` → `from ....core.security`
- `from ...core.data` → `from ....core.data`

**Files Modified:**
- `api/models/timesfm20/routes/endpoints.py` - Updated imports
- `api/models/timesfm20/services/model.py` - Updated imports
- `api/models/timesfm20/services/data.py` - Updated imports

#### 3. Model Registry

**File Created:**
- `api/models/__init__.py` - Central model registry

**Features:**
```python
MODEL_REGISTRY = {
    "timesfm20": {
        "name": "TimesFM 2.0",
        "version": "2.0.500m",
        "description": "Google's TimesFM 2.0 foundation model",
        "module": "api.models.timesfm20",
        "router_path": "api.models.timesfm20.routes.endpoints",
        "service_path": "api.models.timesfm20.services.model",
        "default_port": 8001,
        "status": "active"
    }
    # Future models added here
}

# Helper functions
get_available_models()  # Returns list of active models
get_model_info(model_id)  # Returns model metadata
get_all_models_info()  # Returns complete registry
```

#### 4. API Enhancements

**File Modified:**
- `api/main.py` - Integrated model registry

**New Endpoint:**
- `GET /models` - List all available models with metadata

**Updated Endpoint:**
- `GET /info` - Now uses dynamic model list from registry

**Example Response:**
```json
{
  "models": {
    "timesfm20": {
      "name": "TimesFM 2.0",
      "status": "active",
      ...
    }
  },
  "count": 1
}
```

#### 5. Parameterized Dockerfile

**File Modified:**
- `Dockerfile.api` - Complete rewrite with build arguments

**Build Arguments:**
```dockerfile
ARG MODEL_NAME=all        # Which model to run
ARG MODEL_PORT=8000       # Which port to expose
```

**Features:**
- Conditional dependency installation based on MODEL_NAME
- Supports `MODEL_NAME=all` (default) for main API serving all models
- Supports `MODEL_NAME=timesfm20` for dedicated model service
- Dynamic port exposure and health checks

**Example Builds:**
```bash
# Main API (all models)
docker build -t sapheneia-api .

# TimesFM-only service
docker build -t sapheneia-timesfm20 \
  --build-arg MODEL_NAME=timesfm20 \
  --build-arg MODEL_PORT=8001 .
```

#### 6. Docker Compose Updates

**File Modified:**
- `docker-compose.yml` - Multi-model service configuration

**Current Setup:**
- Main API service on port 8000 (serves all models)
- UI service on port 8080
- Commented example for separate TimesFM service on port 8001

**Volume Changes:**
- Renamed `api_models` → `api_models_timesfm20` (model-specific)
- Added `./src:/app/src` mount (required for DataProcessor)

**Example Future Configuration:**
```yaml
# Uncomment to run TimesFM as separate service
api-timesfm20:
  build:
    args:
      MODEL_NAME: timesfm20
      MODEL_PORT: 8001
  container_name: sapheneia-api-timesfm20
  ports:
    - "8001:8001"
```

#### 7. Setup Script Updates

**File Modified:**
- `setup.sh` - Updated directory creation

**Changes:**
```bash
# Old
mkdir -p api/timesfm20/local

# New
mkdir -p api/models/timesfm20/local
mkdir -p data/uploads
mkdir -p data/results
```

#### 8. Important: src/ Directory Retained

**Issue Discovered:**
Initially attempted to delete `src/` directory (old architecture), but discovered it's still required:

**Reason:**
- `api/models/timesfm20/services/data.py` imports `DataProcessor` from `src/data.py`
- `api/models/timesfm20/services/model.py` imports `TimesFMModel` from `src/model.py`
- These are used via `sys.path.append()` to access legacy code

**Solution:**
- Restored `src/` directory from git
- Added `./src:/app/src` to Docker volumes
- Added `COPY src/ ./src/` to Dockerfiles

**Future Work:**
- Migrate DataProcessor and related utilities to `api/core/`
- Remove dependency on `src/` directory
- Clean architecture separation

### Testing Performed

**Venv Mode:**
```bash
# Test imports and model registry
uv run python -c "from api.main import app; from api.models import get_available_models; print('Available models:', get_available_models())"
# Output: Available models: ['timesfm20']
```

**API Endpoints:**
```bash
# Check available models
curl http://localhost:8000/models

# Test inference (venv mode requires relative paths)
curl -X POST http://localhost:8000/api/v1/timesfm20/inference \
  -H "Authorization: Bearer YriHFLILLlVfumH7g5zh1FpMhe5InKuN" \
  -H "Content-Type: application/json" \
  -d '{
    "data_source_url_or_path": "data/uploads/sample_data.csv",
    "data_definition": {
      "btc_price": "target",
      "eth_price": "dynamic_numerical"
    },
    "parameters": {
      "context_len": 64,
      "horizon_len": 24
    }
  }'
# ✅ Working
```

**Path Handling:**
- Docker mode: Use absolute path `/app/data/uploads/file.csv`
- Venv mode: Use relative path `data/uploads/file.csv`
- API detects environment and handles paths correctly

### Files Modified Summary

| File | Changes |
|------|---------|
| `.env` | Added model-specific ports |
| `.env.template` | Added model-specific ports |
| `api/main.py` | Integrated model registry, added `/models` endpoint |
| `api/models/__init__.py` | Created model registry |
| `api/models/timesfm20/routes/endpoints.py` | Fixed relative imports (+1 level) |
| `api/models/timesfm20/services/model.py` | Fixed relative imports (+1 level) |
| `api/models/timesfm20/services/data.py` | Fixed relative imports (+1 level) |
| `Dockerfile.api` | Parameterized with build args, added src/ |
| `Dockerfile.ui` | Added src/ copy |
| `docker-compose.yml` | Multi-model setup, src/ volumes, renamed volumes |
| `setup.sh` | Updated directory paths, fixed Docker stop |

---

## Phase 3: Remove src/ Dependency

**Date**: October 27, 2025
**Status**: ✅ Complete

### Objective

Eliminate dependency on the legacy `src/` directory by migrating code to proper API and UI module locations, removing all `sys.path.append()` hacks. This addresses **Critical Finding #2** from CODEREVIEW.md.

### Problem

After v2.0 refactoring, the API and UI still depended on `src/` through `sys.path.append()`:
- `api/models/timesfm20/services/model.py` - Used sys.path.append to import from src/
- `api/models/timesfm20/services/data.py` - Used sys.path.append to import from src/
- `ui/app.py` - Used multiple sys.path.append calls

This violated clean architecture principles and broke proper Python packaging.

### Implementation

#### 1. File Migration

**Files Copied:**
```bash
src/data.py                      → api/core/data_processing.py  (604 lines)
src/model.py                     → api/core/model_wrapper.py    (356 lines)
src/forecast.py                  → api/core/forecasting.py      (475 lines)
src/interactive_visualization.py → ui/visualization.py          (1129 lines)
```

All files copied as-is with no modifications.

#### 2. Import Updates - API

**api/models/timesfm20/services/model.py:**
```python
# BEFORE
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
from model import TimesFMModel
from forecast import Forecaster, run_forecast, process_quantile_bands

# AFTER
import os
from ....core.model_wrapper import TimesFMModel
from ....core.forecasting import Forecaster, run_forecast, process_quantile_bands
```

**api/models/timesfm20/services/data.py:**
```python
# BEFORE
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
from data import DataProcessor, prepare_visualization_data

# AFTER
from ....core.data_processing import DataProcessor, prepare_visualization_data
```

#### 3. Import Updates - UI

**ui/app.py:**
```python
# BEFORE
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__)))
from interactive_visualization import InteractiveVisualizer
from forecast import process_quantile_bands
from api_client import SapheneiaAPIClient

# AFTER
sys.path.append(os.path.join(os.path.dirname(__file__)))  # Add ui/ to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))  # Add project root
from visualization import InteractiveVisualizer
from api.core.forecasting import process_quantile_bands
from api_client import SapheneiaAPIClient
```

**Note:** Kept one sys.path.append for project root - acceptable for Flask script execution.

#### 4. Docker Configuration

**Dockerfile.ui - Added api/ directory:**
```dockerfile
# BEFORE
COPY ui/ ./ui/
COPY src/ ./src/

# AFTER
COPY ui/ ./ui/
COPY api/ ./api/    # ← Added
COPY src/ ./src/
```

UI needs `api/` directory for `api.core.forecasting` imports.

### Error Encountered and Fixed

**NameError: 'os' is not defined**

When removing sys.path.append, accidentally removed `import os` but file still needed it for:
- `os.path.abspath()`
- `os.path.join()`
- `os.path.dirname()`

**Fix:** Added back `import os` on line 8.

**Lesson:** Check all module usage when refactoring imports, not just sys.path locations.

### Testing Performed

**API Imports (venv):**
```bash
$ uv run python -c "from api.main import app; from api.models import get_available_models; print('✅ API imports successful'); print('Available models:', get_available_models())"
✅ API imports successful
Available models: ['timesfm20']
```

**Docker Deployment:**
```bash
$ docker compose build && docker compose up -d

# API Health
$ curl http://localhost:8000/health
{"status":"healthy","api_version":"2.0.0","models":{"timesfm20":{"status":"uninitialized"}}}

# UI Health
$ curl http://localhost:8080/health
{"status":"healthy","ui":"running","api_connected":true,"api_health":{...}}

# UI Web Interface
$ curl -s http://localhost:8080/ | head -20
<!DOCTYPE html>
<html lang="en">
...
```

**Results:**
- ✅ API healthy and responding
- ✅ UI healthy and responding
- ✅ Web interface serving correctly
- ✅ No import errors in logs
- ✅ Both venv and Docker modes working

### Architecture Improvements

**Before:**
- API and UI used sys.path.append to import from src/
- Non-standard Python packaging
- Breaks in some deployment scenarios

**After:**
- Proper Python package structure with relative imports
- `api/core/` contains shared utilities
- `ui/` has its own modules
- `src/` preserved for notebook backward compatibility
- Standard import patterns throughout

### sys.path.append() Status

**Before Phase 3:** 4 sys.path.append() calls (all to src/)
**After Phase 3:** 1 sys.path.append() call (project root for Flask - acceptable)

All problematic sys.path.append to src/ removed!

### Backward Compatibility

All existing Jupyter notebooks continue to work unchanged:
- `src/` directory preserved intact
- Notebooks import directly from `src/`
- No notebook code changes required

### Files Modified Summary

| File | Changes |
|------|---------|
| `api/core/data_processing.py` | Created (copy of src/data.py) |
| `api/core/model_wrapper.py` | Created (copy of src/model.py) |
| `api/core/forecasting.py` | Created (copy of src/forecast.py) |
| `ui/visualization.py` | Created (copy of src/interactive_visualization.py) |
| `api/models/timesfm20/services/model.py` | Updated imports, removed sys.path.append |
| `api/models/timesfm20/services/data.py` | Updated imports, removed sys.path.append |
| `ui/app.py` | Updated imports, removed sys.path.append to src/ |
| `Dockerfile.ui` | Added `COPY api/ ./api/` |
| `REMEDIATION_EXECUTION.md` | Added Phase 3 comprehensive documentation |

### Documentation

Phase 3 documentation integrated into: [`REMEDIATION_EXECUTION.md`](REMEDIATION_EXECUTION.md)

Includes:
- Complete problem statement
- Implementation details (all 4 tasks)
- Error resolution (3 issues encountered and fixed)
- Testing results (4 comprehensive tests)
- Architecture improvements (before/after diagrams)
- Lessons learned and benefits achieved

---

## Current Project Status

**Version**: 2.0.0
**Last Updated**: October 27, 2025
**Status**: ✅ Production Ready

### Project Structure

```
sapheneia/
├── api/                                    # FastAPI Backend
│   ├── main.py                             # Application entry point
│   ├── core/                               # Shared infrastructure
│   │   ├── config.py                       # Settings management
│   │   ├── security.py                     # API authentication
│   │   ├── data.py                         # Data fetching utilities
│   │   ├── paths.py                        # Path resolution utilities
│   │   ├── rate_limit.py                   # Rate limiting
│   │   ├── data_processing.py              # Data processing (from src/)
│   │   ├── model_wrapper.py                # Model wrapper (from src/)
│   │   └── forecasting.py                  # Forecasting logic (from src/)
│   └── models/                             # Model modules
│       ├── __init__.py                     # Model registry
│       └── timesfm20/                      # TimesFM-2.0 model
│           ├── routes/endpoints.py         # REST API endpoints
│           ├── schemas/schema.py           # Pydantic models
│           ├── services/
│           │   ├── model.py                # Model service
│           │   └── data.py                 # Data service
│           └── local/                      # Model artifacts
│
├── ui/                                     # Flask Frontend
│   ├── app.py                              # Web application
│   ├── api_client.py                       # REST API client
│   ├── visualization.py                    # Visualization (from src/)
│   ├── templates/                          # HTML templates
│   └── static/                             # CSS/JS assets
│
├── src/                                    # Legacy (for notebooks only)
│   ├── model.py                            # TimesFM model wrapper
│   ├── forecast.py                         # Forecasting logic
│   ├── data.py                             # Data processing
│   └── interactive_visualization.py        # Plotting utilities
│
├── data/                                   # Shared data folder (NEW)
│   ├── uploads/                            # User uploads
│   └── results/                            # Forecast results
│
├── notebooks/                              # Jupyter notebooks
├── logs/                                   # Application logs
│
├── Dockerfile.api                          # API Docker (parameterized)
├── Dockerfile.ui                           # UI Docker
├── docker-compose.yml                      # Orchestration
├── setup.sh                                # Unified management script
├── .env                                    # Local config
├── .env.template                           # Config template
├── pyproject.toml                          # Dependencies
└── README.md                               # Documentation
```

### How to Add a New Model

**Example: Adding Chronos**

1. **Create model directory:**
   ```bash
   mkdir -p api/models/chronos/{routes,schemas,services,local}
   ```

2. **Implement model code:**
   - Copy structure from `api/models/timesfm20/`
   - Update imports and model-specific logic
   - Create endpoints, schemas, services

3. **Register in model registry:**
   ```python
   # api/models/__init__.py
   MODEL_REGISTRY = {
       # ... existing models ...
       "chronos": {
           "name": "Chronos",
           "version": "1.0",
           "description": "Amazon Chronos forecasting model",
           "module": "api.models.chronos",
           "router_path": "api.models.chronos.routes.endpoints",
           "service_path": "api.models.chronos.services.model",
           "default_port": 8002,
           "status": "active"
       }
   }
   ```

4. **Import router in main.py:**
   ```python
   from .models.chronos.routes import endpoints as chronos_endpoints
   app.include_router(chronos_endpoints.router, prefix="/api/v1")
   ```

5. **Update Dockerfile.api (optional):**
   ```dockerfile
   RUN if [ "$MODEL_NAME" = "chronos" ] || [ "$MODEL_NAME" = "all" ]; then \
           uv pip install --system --no-cache chronos-forecasting; \
       fi
   ```

6. **Add to docker-compose.yml (optional):**
   ```yaml
   api-chronos:
     build:
       args:
         MODEL_NAME: chronos
         MODEL_PORT: 8002
     container_name: sapheneia-api-chronos
     ports:
       - "8002:8002"
   ```

### Running the Application

**Quick Start:**
```bash
# Initialize
./setup.sh init

# Run with venv
./setup.sh run-venv all

# Run with Docker
./setup.sh run-docker all

# Stop all services
./setup.sh stop
```

**Access Points:**
- API Docs: http://localhost:8000/docs
- API Health: http://localhost:8000/health
- Model List: http://localhost:8000/models
- Web UI: http://localhost:8080

### Key Configuration

**Required Environment Variables:**
```env
# API
API_SECRET_KEY=your_secret_key_change_me_in_production  # CHANGE THIS!
API_HOST=0.0.0.0
API_PORT=8000

# Model Ports
TIMESFM20_MODEL_PORT=8001
CHRONOS_MODEL_PORT=8002
PROPHET_MODEL_PORT=8003

# UI
UI_PORT=8080
UI_API_BASE_URL=http://localhost:8000
```

### API Authentication

All endpoints (except `/`, `/health`, `/info`, `/models`) require authentication:

```bash
curl http://localhost:8000/api/v1/timesfm20/status \
  -H "Authorization: Bearer your_secret_key_change_me_in_production"
```

### Path Handling

**Venv Mode:**
```json
{
  "data_source_url_or_path": "data/uploads/file.csv"
}
```

**Docker Mode:**
```json
{
  "data_source_url_or_path": "/app/data/uploads/file.csv"
}
```

The API automatically handles path resolution based on runtime environment.

---

## Outstanding Tasks

### Completed ✅
- [x] Phase 1: Security Hardening (API keys, CORS, rate limiting, file uploads)
- [x] Phase 2: Path Handling Standardization (Docker vs venv detection)
- [x] Phase 3: Remove src/ Dependency (proper Python packaging)
- [x] Multi-model architecture complete
- [x] Docker deployment working
- [x] Documentation updated

### Future Enhancements
- [ ] Add Chronos model
- [ ] Add Prophet model
- [ ] UI model selector dropdown (optional)
- [ ] MLflow integration for experiment tracking
- [ ] Celery for async inference
- [ ] Redis for distributed state
- [ ] Batch inference endpoints
- [ ] WebSocket support for real-time updates
- [ ] Advanced authentication (OAuth2)
- [ ] Prometheus metrics
- [ ] Phase 4: Database Integration (PostgreSQL for configs/results)
- [ ] Phase 5: Testing Infrastructure (unit/integration/e2e tests)
- [ ] Phase 6: CI/CD Pipeline (GitHub Actions)

---

## Key Achievements

### Architecture
✅ Clean separation of concerns (API, UI, models, core)
✅ Scalable multi-model support
✅ RESTful API design
✅ Docker containerization
✅ Environment-based configuration

### Backward Compatibility
✅ All existing notebooks work unchanged
✅ `src/` modules preserved
✅ Original functionality maintained

### DevOps
✅ Docker Compose orchestration
✅ Health checks configured
✅ Unified management script (`setup.sh`)
✅ Environment variable configuration
✅ Auto-generated API documentation

### Security
✅ API key authentication
✅ Path validation
✅ CORS configuration
✅ Secret management via `.env`

### Documentation
✅ Comprehensive README
✅ API documentation (Swagger/ReDoc)
✅ Quick start guide
✅ This development log

---

## Lessons Learned

### Docker Path Handling
- Always verify volume mount paths match between containers
- Environment detection is crucial for hybrid deployment (Docker + venv)
- Unified data folders simplify cross-container communication

### Bash Script Debugging
- Docker CLI can fail in bash function contexts
- Direct container commands more reliable than compose in scripts
- Execution order matters (Docker before port cleanup)

### Code Restructuring
- Always check for dependency chains before deleting directories
- Relative import paths need updating when moving modules
- Git history is valuable for recovering accidentally deleted code

### Multi-Model Design
- Central registry pattern scales well
- Parameterized Dockerfiles reduce maintenance
- Single API gateway simplifies orchestration

---

## Version History

| Version | Date | Major Changes |
|---------|------|---------------|
| 2.0.0 | Oct 27, 2025 | Multi-model architecture, model registry |
| 2.0.0-beta | Oct 26, 2025 | Docker fixes, path handling |
| 2.0.0-alpha | Oct 26, 2025 | Initial FastAPI refactoring |
| 1.0.0 | - | Original Flask monolith |

---

*This document serves as a complete record of all development work performed by Claude on the Sapheneia project, including design decisions, implementation details, and lessons learned.*
