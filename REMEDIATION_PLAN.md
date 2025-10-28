# Sapheneia v2.0 Remediation Plan

**Date**: October 27, 2025
**Based On**: Code Review Report (CODEREVIEW.md)
**Status**: Planning Phase

---

## Executive Summary

This plan addresses the critical and major issues identified in the code review, prioritized by impact and effort. The goal is to make Sapheneia production-ready within 2-3 weeks.

**Priorities:**
1. **Critical Security Issues** - Must fix before any production deployment
2. **Path Handling** - Blocking user experience issues
3. **Architecture Cleanup** - Remove technical debt (src/ dependency)
4. **Testing** - Enable safe refactoring and deployment
5. **Scalability** - Prepare for horizontal scaling

---

## Phase 1: Security Hardening (Week 1, Days 1-2)

**Goal**: Fix all critical security vulnerabilities
**Effort**: 1-2 days
**Priority**: 🔴 CRITICAL

### Task 1.1: API Key Validation
**Issue**: Default API key in code without validation

**Implementation**:
```python
# api/core/config.py
def validate_api_key(self):
    """Validate API key security."""
    if self.API_SECRET_KEY == "default_secret_key_please_change":
        if os.getenv('ENVIRONMENT') == 'production':
            raise ValueError(
                "❌ CRITICAL SECURITY ERROR: API_SECRET_KEY must be changed!\n"
                "Set a strong secret key in your .env file."
            )
        logger.warning("⚠️  WARNING: Using default API_SECRET_KEY!")
        logger.warning("⚠️  CHANGE THIS IN PRODUCTION!")

    # Validate key strength
    if len(self.API_SECRET_KEY) < 32:
        logger.warning(f"⚠️  API key is weak (length: {len(self.API_SECRET_KEY)})")
        logger.warning("⚠️  Recommended: 32+ characters")

# Call in settings initialization
settings = Settings()
settings.validate_api_key()
```

**Files to modify**:
- `api/core/config.py`
- `.env.template` - Add guidance on generating strong keys

**Acceptance criteria**:
- ✅ Application refuses to start in production with default key
- ✅ Warning logged in development mode
- ✅ Validation runs on startup

---

### Task 1.2: CORS Configuration
**Issue**: Too permissive CORS settings

**Implementation**:
```python
# api/core/config.py
class Settings(BaseSettings):
    # ...
    CORS_ORIGINS: str = "http://localhost:8080,http://127.0.0.1:8080"
    CORS_METHODS: str = "GET,POST,OPTIONS"
    CORS_HEADERS: str = "Authorization,Content-Type"

# api/main.py
allowed_origins = settings.CORS_ORIGINS.split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS.split(','),
    allow_headers=settings.CORS_HEADERS.split(','),
)
```

**Files to modify**:
- `api/core/config.py`
- `api/main.py`
- `.env.template`
- `README.md` - Document CORS configuration

**Acceptance criteria**:
- ✅ CORS configurable via environment variables
- ✅ Restrictive defaults for production
- ✅ Documentation updated

---

### Task 1.3: Rate Limiting
**Issue**: No rate limiting on API endpoints

**Implementation**:
```python
# Add to pyproject.toml
dependencies = [
    # ... existing ...
    "slowapi>=0.1.9",
]

# api/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# api/models/timesfm20/routes/endpoints.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/inference")
@limiter.limit("5/minute")  # 5 requests per minute
async def inference_endpoint(...):
    ...

@router.post("/initialization")
@limiter.limit("2/minute")  # 2 initializations per minute
async def initialization_endpoint(...):
    ...

@router.get("/status")
@limiter.limit("20/minute")  # 20 status checks per minute
async def status_endpoint(...):
    ...
```

**Files to modify**:
- `pyproject.toml`
- `api/main.py`
- `api/models/timesfm20/routes/endpoints.py`
- `api/core/config.py` - Add rate limit configuration
- `README.md` - Document rate limits

**Acceptance criteria**:
- ✅ Rate limits enforced on all model endpoints
- ✅ Different limits for different endpoint types
- ✅ Configurable via environment variables
- ✅ Returns HTTP 429 when limit exceeded

---

### Task 1.4: File Upload Security
**Issue**: Insufficient file validation

**Implementation**:
```python
# ui/app.py
import magic  # python-magic for MIME type detection

ALLOWED_MIME_TYPES = {
    'text/csv',
    'text/plain',
    'application/vnd.ms-excel',
}

def validate_file_upload(file):
    """Validate uploaded file for security."""
    # Check file extension
    if not allowed_file(file.filename):
        raise ValueError("Invalid file extension")

    # Check MIME type
    mime = magic.from_buffer(file.read(1024), mime=True)
    file.seek(0)  # Reset file pointer

    if mime not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Invalid file type: {mime}")

    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    if size > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {size} bytes")

    # Basic content validation for CSV
    if mime == 'text/csv':
        try:
            df = pd.read_csv(file, nrows=1)
            file.seek(0)
        except Exception as e:
            raise ValueError(f"Invalid CSV file: {e}")

    return True
```

**Files to modify**:
- `ui/app.py`
- `pyproject.toml` - Add `python-magic`
- `README.md` - Document file requirements

**Acceptance criteria**:
- ✅ MIME type validation
- ✅ Content validation for CSV files
- ✅ Clear error messages for users

---

## Phase 2: Path Handling Standardization (Week 1, Days 3-4)

**Goal**: Fix all path handling inconsistencies
**Effort**: 1-2 days
**Priority**: 🔴 CRITICAL

### Task 2.1: Create Path Utility Module
**Issue**: Inconsistent path handling across venv and Docker

**Implementation**:
```python
# api/core/paths.py
"""Path handling utilities for Sapheneia.

Provides consistent path resolution across venv and Docker environments.
"""
import os
from pathlib import Path
from typing import Union

# Detect environment
IS_DOCKER = os.path.exists('/app')
PROJECT_ROOT = Path('/app') if IS_DOCKER else Path(__file__).parent.parent.parent

# Base directories
DATA_DIR = PROJECT_ROOT / 'data'
UPLOADS_DIR = DATA_DIR / 'uploads'
RESULTS_DIR = DATA_DIR / 'results'
LOGS_DIR = PROJECT_ROOT / 'logs'


def normalize_data_path(path: Union[str, Path]) -> Path:
    """
    Normalize a data file path for the current environment.

    Handles:
    - Absolute paths (/app/data/uploads/file.csv)
    - Relative paths (data/uploads/file.csv)
    - Prefixed paths (local://data/uploads/file.csv)
    - Bare filenames (file.csv) - assumes uploads dir

    Args:
        path: Input path in any format

    Returns:
        Absolute Path object for the current environment

    Raises:
        ValueError: If path is outside allowed directories
    """
    # Convert to string
    path_str = str(path)

    # Remove local:// prefix if present
    if path_str.startswith('local://'):
        path_str = path_str.replace('local://', '')

    # Convert to Path object
    path_obj = Path(path_str)

    # Handle absolute paths
    if path_obj.is_absolute():
        # If Docker path in venv, convert
        if not IS_DOCKER and str(path_obj).startswith('/app/'):
            path_str = str(path_obj).replace('/app/', '')
            path_obj = PROJECT_ROOT / path_str
        # If venv path in Docker, convert
        elif IS_DOCKER and not str(path_obj).startswith('/app/'):
            path_obj = PROJECT_ROOT / path_obj.relative_to(path_obj.anchor)
    else:
        # Handle relative paths
        if path_str.startswith('data/'):
            path_obj = PROJECT_ROOT / path_str
        elif '/' not in path_str:
            # Bare filename - assume uploads directory
            path_obj = UPLOADS_DIR / path_str
        else:
            # Other relative path - resolve from project root
            path_obj = PROJECT_ROOT / path_str

    # Resolve to absolute path
    path_obj = path_obj.resolve()

    # Security: Ensure path is within data directory
    try:
        path_obj.relative_to(DATA_DIR)
    except ValueError:
        raise ValueError(
            f"Security: Path '{path}' is outside allowed data directory.\n"
            f"Resolved to: {path_obj}\n"
            f"Allowed: {DATA_DIR}"
        )

    return path_obj


def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure directory exists, creating if necessary."""
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def get_upload_path(filename: str) -> Path:
    """Get path for uploaded file."""
    return UPLOADS_DIR / filename


def get_result_path(filename: str) -> Path:
    """Get path for result file."""
    return RESULTS_DIR / filename


# Initialize directories on module import
for directory in [DATA_DIR, UPLOADS_DIR, RESULTS_DIR, LOGS_DIR]:
    ensure_directory(directory)
```

**Files to create**:
- `api/core/paths.py`

**Acceptance criteria**:
- ✅ Single source of truth for path handling
- ✅ Works identically in venv and Docker
- ✅ Security validation built-in
- ✅ Clear error messages

---

### Task 2.2: Update Data Fetching Service
**Issue**: Incomplete path resolution in fetch_data_source

**Implementation**:
```python
# api/core/data.py
from .paths import normalize_data_path

def fetch_data_source(source_url_or_path: str) -> pd.DataFrame:
    """
    Fetches data from a specified source URL or local path.

    Args:
        source_url_or_path: URL or path to the data source
            - URLs: "http://example.com/data.csv"
            - Absolute paths: "/app/data/uploads/file.csv"
            - Relative paths: "data/uploads/file.csv"
            - Filenames: "file.csv" (assumes uploads dir)
            - Prefixed: "local://data/uploads/file.csv"

    Returns:
        DataFrame loaded from source
    """
    logger.info(f"Fetching data from: {source_url_or_path}")

    # Check if URL
    if source_url_or_path.startswith(("http://", "https://")):
        return _fetch_http_url(source_url_or_path)

    # Check if cloud storage (future)
    if source_url_or_path.startswith(("s3://", "gs://")):
        raise NotImplementedError("Cloud storage support coming soon")

    # Otherwise, treat as local file
    file_path = normalize_data_path(source_url_or_path)

    logger.info(f"Resolved to local path: {file_path}")

    return _fetch_local_file(file_path)


def _fetch_local_file(file_path: Path) -> pd.DataFrame:
    """
    Fetch data from a local file.

    Args:
        file_path: Resolved Path object (from normalize_data_path)
    """
    # Check if file exists
    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}\n"
            f"Make sure the file is in the data/uploads directory."
        )

    # Determine file type
    file_extension = file_path.suffix.lower()

    try:
        if file_extension == ".csv":
            data = pd.read_csv(file_path)
            logger.info(f"Loaded CSV with shape: {data.shape}")
            return data
        elif file_extension == ".json":
            data = pd.read_json(file_path)
            logger.info(f"Loaded JSON with shape: {data.shape}")
            return data
        elif file_extension in [".xlsx", ".xls"]:
            data = pd.read_excel(file_path)
            logger.info(f"Loaded Excel with shape: {data.shape}")
            return data
        else:
            raise DataFetchError(
                f"Unsupported file format: {file_extension}\n"
                f"Supported: .csv, .json, .xlsx, .xls"
            )
    except Exception as e:
        logger.error(f"Failed to load file: {e}")
        raise DataFetchError(f"Failed to load file: {e}")
```

**Files to modify**:
- `api/core/data.py`

**Acceptance criteria**:
- ✅ Uses new path normalization utility
- ✅ Works in both venv and Docker
- ✅ Clear error messages with hints
- ✅ Security validation automatic

---

### Task 2.3: Update UI File Handling
**Issue**: UI uses inconsistent path handling

**Implementation**:
```python
# ui/app.py
import sys
sys.path.append('..')  # Add parent to path
from api.core.paths import get_upload_path, get_result_path, IS_DOCKER

# Configuration
UPLOAD_FOLDER = str(get_upload_path(''))
RESULTS_FOLDER = str(get_result_path(''))

@app.route('/forecast', methods=['POST'])
def forecast():
    # ... existing code ...

    # Save uploaded file
    filename = secure_filename(file.filename)
    filepath = get_upload_path(filename)
    file.save(str(filepath))

    # Send to API - use just the filename
    # API will resolve the path correctly
    api_response = api_client.run_inference(
        filename=filename,  # Just filename, not full path
        data_definition=data_definition,
        parameters=parameters
    )
```

**Files to modify**:
- `ui/app.py`
- `ui/api_client.py`

**Acceptance criteria**:
- ✅ UI uses path utilities
- ✅ Sends simple filenames to API
- ✅ API resolves paths correctly

---

## Phase 3: Remove src/ Dependency (Week 1, Days 5-7)

**Goal**: Eliminate sys.path manipulation and move code to proper modules
**Effort**: 2-3 days
**Priority**: 🟡 HIGH

### Task 3.1: Migrate DataProcessor
**Issue**: DataProcessor used via sys.path from src/

**Implementation**:
```python
# api/core/data_processing.py
"""
Data processing utilities for time series forecasting.

Migrated from src/data.py to remove sys.path dependency.
"""
# Copy DataProcessor class from src/data.py
# Update imports to use local modules
# Add type hints and documentation
```

**Steps**:
1. Copy `DataProcessor` class from `src/data.py`
2. Create `api/core/data_processing.py`
3. Update imports in class
4. Add comprehensive docstrings
5. Update `api/models/timesfm20/services/data.py` to import from new location

**Files to create**:
- `api/core/data_processing.py`

**Files to modify**:
- `api/models/timesfm20/services/data.py`

**Acceptance criteria**:
- ✅ No sys.path manipulation
- ✅ Proper module imports
- ✅ All tests pass (when added)

---

### Task 3.2: Migrate TimesFM Model Wrapper
**Issue**: TimesFMModel wrapper used via sys.path

**Implementation**:
```python
# api/core/models/__init__.py
# api/core/models/timesfm_wrapper.py
"""
TimesFM model wrapper for consistent model management.

Migrated from src/model.py.
"""
```

**Steps**:
1. Create `api/core/models/` directory
2. Copy `TimesFMModel` from `src/model.py`
3. Update imports
4. Add type hints
5. Update services to use new location

**Files to create**:
- `api/core/models/__init__.py`
- `api/core/models/timesfm_wrapper.py`

**Files to modify**:
- `api/models/timesfm20/services/model.py`

---

### Task 3.3: Migrate Forecasting Logic
**Issue**: Forecaster class used via sys.path

**Implementation**:
```python
# api/core/forecast.py
"""
Forecasting utilities and logic.

Migrated from src/forecast.py.
"""
```

**Steps**:
1. Copy forecasting logic from `src/forecast.py`
2. Create `api/core/forecast.py`
3. Update imports
4. Update services

**Files to create**:
- `api/core/forecast.py`

**Files to modify**:
- `api/models/timesfm20/services/model.py`

---

### Task 3.4: Archive src/ Directory
**Issue**: Remove dependency once migration complete

**Steps**:
1. Verify all tests pass with new imports
2. Move `src/` to `archive/src/` for reference
3. Update notebooks to use new imports (optional)
4. Update documentation

**Files to modify**:
- Move `src/` → `archive/src/`
- Update `Dockerfile.api` - remove src/ copy
- Update `Dockerfile.ui` - remove src/ copy
- Update `docker-compose.yml` - remove src/ volumes
- Update `README.md` - update documentation

---

## Phase 4: State Management (Week 2, Days 1-3)

**Goal**: Replace module-level state with proper state management
**Effort**: 2-3 days
**Priority**: 🟡 HIGH

### Task 4.1: Document Current Limitations
**Quick fix for now**

**Implementation**:
```python
# api/main.py startup
@app.on_event("startup")
async def startup_event():
    logger.warning("=" * 80)
    logger.warning("⚠️  SCALING LIMITATION")
    logger.warning("⚠️  This API uses module-level state management")
    logger.warning("⚠️  Only run with --workers 1 (single worker)")
    logger.warning("⚠️  Horizontal scaling requires Redis state backend")
    logger.warning("=" * 80)
```

**Files to modify**:
- `api/main.py`
- `README.md` - Add deployment limitations section
- `docker-compose.yml` - Add comment about workers

**Acceptance criteria**:
- ✅ Clear warning on startup
- ✅ Documentation updated
- ✅ Users aware of limitation

---

### Task 4.2: Add Thread Safety (Intermediate)
**Better than nothing**

**Implementation**:
```python
# api/models/timesfm20/services/model.py
import threading

_model_lock = threading.Lock()

def initialize_model(...):
    """Initialize model with thread safety."""
    global _model_status

    with _model_lock:
        if _model_status == "initializing":
            raise ModelInitializationError("Initialization in progress")

        if _model_status == "ready":
            logger.warning("Model already initialized")
            return

        _model_status = "initializing"

    try:
        # ... initialization code ...
        with _model_lock:
            _model_status = "ready"
    except Exception as e:
        with _model_lock:
            _model_status = "error"
            _error_message = str(e)
        raise
```

**Files to modify**:
- `api/models/timesfm20/services/model.py`

---

### Task 4.3: Redis State Backend (Future)
**Long-term solution**

**Implementation**:
```python
# api/core/state.py
"""
State management using Redis for horizontal scaling.
"""
import redis
from typing import Optional, Any
import json

class StateManager:
    """Distributed state management using Redis."""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    def get_model_status(self, model_id: str) -> str:
        """Get model status from Redis."""
        status = self.redis.get(f"model:{model_id}:status")
        return status.decode() if status else "uninitialized"

    def set_model_status(self, model_id: str, status: str):
        """Set model status in Redis."""
        self.redis.set(f"model:{model_id}:status", status)

    def acquire_lock(self, key: str, timeout: int = 30):
        """Acquire distributed lock."""
        return self.redis.lock(key, timeout=timeout)
```

**Note**: This is Phase 3 (Long-term), not immediate

---

## Phase 5: API Endpoint Improvements (Week 2, Days 4-5)

**Goal**: Fix inconsistencies and improve API endpoint design
**Effort**: 1-2 days
**Priority**: 🟡 HIGH

### Issues to Address

From `CODEREVIEW.md`:
1. **Major Issue #5**: Missing validation in endpoints (lines 239-278)
   - Input validation incomplete
   - No request body size limits
   - Missing field validators
   - Inconsistent error responses

2. **Major Issue #6**: Inconsistent response formats (lines 279-323)
   - Some endpoints return raw data, others wrapped
   - Missing pagination
   - No response schemas defined
   - Inconsistent error format

### Task 5.1: Standardize Request Validation

**Objective**: Add comprehensive validation to all API endpoints

**Implementation**:
```python
# api/models/timesfm20/schemas/schema.py

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, List, Any
from datetime import datetime

class InferenceInput(BaseModel):
    """Request schema for inference endpoint."""

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
        description="Forecasting parameters"
    )

    @field_validator('data_definition')
    @classmethod
    def validate_data_definition(cls, v: Dict[str, str]) -> Dict[str, str]:
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


class InitializationInput(BaseModel):
    """Request schema for initialization endpoint."""

    backend: str = Field(
        default="cpu",
        description="Model backend (cpu, gpu, or mps)",
        pattern="^(cpu|gpu|mps)$"
    )

    context_len: int = Field(
        default=64,
        description="Context length for model",
        ge=1,
        le=512
    )

    horizon_len: int = Field(
        default=24,
        description="Forecast horizon length",
        ge=1,
        le=365
    )

    checkpoint_path: Optional[str] = Field(
        default=None,
        description="Path to model checkpoint",
        max_length=1024
    )

    quantiles: List[float] = Field(
        default=[0.1, 0.5, 0.9],
        description="Quantiles for prediction intervals",
        min_length=1,
        max_length=20
    )

    @field_validator('quantiles')
    @classmethod
    def validate_quantiles(cls, v: List[float]) -> List[float]:
        """Validate quantiles are between 0 and 1."""
        for q in v:
            if not (0 < q < 1):
                raise ValueError(f"quantile {q} must be between 0 and 1")

        # Ensure sorted and unique
        v_sorted = sorted(set(v))
        return v_sorted
```

**Files to modify**:
- `api/models/timesfm20/schemas/schema.py` - Add comprehensive validators
- `api/models/timesfm20/routes/endpoints.py` - Use validated schemas

**Acceptance criteria**:
- ✅ All inputs validated with Pydantic
- ✅ Clear validation error messages
- ✅ Field constraints enforced
- ✅ Type checking automatic

---

### Task 5.2: Standardize Response Formats

**Objective**: Create consistent response structure across all endpoints

**Implementation**:
```python
# api/models/timesfm20/schemas/schema.py

from typing import Generic, TypeVar, Optional
from datetime import datetime

T = TypeVar('T')

class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

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


class StatusResponse(BaseModel):
    """Status endpoint response."""
    model_status: str
    error_message: Optional[str] = None
    model_info: Optional[Dict[str, Any]] = None
    uptime_seconds: Optional[float] = None


class InferenceResponse(BaseModel):
    """Inference endpoint response."""
    forecasts: Dict[str, Any]
    metadata: Dict[str, Any]
    execution_time_seconds: float
    model_version: str


class InitializationResponse(BaseModel):
    """Initialization endpoint response."""
    model_status: str
    model_info: Dict[str, Any]
    initialization_time_seconds: float


# Usage in endpoints
@router.get("/status", response_model=APIResponse[StatusResponse])
async def status_endpoint():
    """Get model status with standardized response."""
    status_data = get_status()

    return APIResponse(
        success=True,
        data=StatusResponse(
            model_status=status_data["status"],
            error_message=status_data.get("error"),
            model_info=status_data.get("info"),
            uptime_seconds=calculate_uptime()
        )
    )
```

**Files to modify**:
- `api/models/timesfm20/schemas/schema.py` - Add response models
- `api/models/timesfm20/routes/endpoints.py` - Use response models
- `api/main.py` - Add response_model to endpoint decorators

**Acceptance criteria**:
- ✅ All endpoints use APIResponse wrapper
- ✅ Consistent structure across endpoints
- ✅ OpenAPI docs show response schemas
- ✅ Error responses follow same format

---

### Task 5.3: Add Request Size Limits

**Objective**: Protect against oversized requests

**Implementation**:
```python
# api/core/config.py
class Settings(BaseSettings):
    # ... existing ...

    # Request limits
    MAX_REQUEST_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024   # 50MB


# api/main.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    """Enforce request size limits."""
    if request.method in ["POST", "PUT", "PATCH"]:
        content_length = request.headers.get("content-length")

        if content_length:
            content_length = int(content_length)
            if content_length > settings.MAX_REQUEST_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "REQUEST_TOO_LARGE",
                        "message": f"Request size {content_length} exceeds maximum {settings.MAX_REQUEST_SIZE} bytes"
                    }
                )

    response = await call_next(request)
    return response
```

**Files to modify**:
- `api/core/config.py` - Add size limit settings
- `api/main.py` - Add middleware
- `.env` / `.env.template` - Add configuration

**Acceptance criteria**:
- ✅ Large requests rejected with 413 status
- ✅ Configurable via environment variables
- ✅ Clear error messages
- ✅ Applies to all endpoints

---

### Task 5.4: Add Response Metadata

**Objective**: Include useful metadata in all responses

**Implementation**:
```python
# api/models/timesfm20/routes/endpoints.py

import time
from datetime import datetime

@router.post("/inference", response_model=APIResponse[InferenceResponse])
async def inference_endpoint(
    input_data: InferenceInput,
    request: Request,
    api_key: str = Depends(get_api_key)
):
    """Run inference with metadata."""
    start_time = time.time()

    # ... existing inference code ...

    execution_time = time.time() - start_time

    return APIResponse(
        success=True,
        data=InferenceResponse(
            forecasts=results,
            metadata={
                "num_forecasts": len(results),
                "columns_used": list(target_inputs.keys()),
                "parameters_used": parameters,
            },
            execution_time_seconds=execution_time,
            model_version=get_model_version()
        ),
        metadata={
            "request_id": str(request.state.request_id),
            "api_version": "2.0.0",
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

**Files to modify**:
- All endpoint functions in `api/models/timesfm20/routes/endpoints.py`

**Acceptance criteria**:
- ✅ Execution time tracked
- ✅ Request ID in metadata
- ✅ Model version in response
- ✅ Useful statistics included

---

### Task 5.5: Add Pagination Support

**Objective**: Add pagination for endpoints that return large datasets (future-proofing)

**Implementation**:
```python
# api/models/timesfm20/schemas/schema.py

class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=1000, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


# Usage (for future batch endpoints)
@router.get("/batch-results", response_model=APIResponse[PaginatedResponse[ForecastResult]])
async def get_batch_results(
    pagination: PaginationParams = Depends()
):
    """Get paginated batch results."""
    # ... pagination logic ...
    pass
```

**Files to create/modify**:
- `api/models/timesfm20/schemas/schema.py` - Add pagination models
- Future batch endpoints

**Acceptance criteria**:
- ✅ Pagination schema defined
- ✅ Ready for future batch endpoints
- ✅ Consistent pagination format

---

## Phase 6: Testing Infrastructure (Week 2, Days 6-7)

**Goal**: Add comprehensive test coverage
**Effort**: 2 days
**Priority**: 🟡 HIGH

### Task 6.1: Setup Test Infrastructure

**Implementation**:
```python
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --cov=api --cov-report=html --cov-report=term"

# tests/conftest.py
"""Pytest configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient
from api.main import app

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)

@pytest.fixture
def auth_headers():
    """Authentication headers for testing."""
    return {"Authorization": "Bearer test_secret_key"}

@pytest.fixture
def sample_data_file(tmp_path):
    """Create sample CSV file for testing."""
    import pandas as pd
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=100),
        'value': range(100),
    })
    file_path = tmp_path / "test_data.csv"
    df.to_csv(file_path, index=False)
    return file_path
```

**Files to create**:
- `tests/conftest.py`
- `tests/__init__.py`

---

### Task 6.2: Unit Tests for Core Modules

**Implementation**:
```python
# tests/core/test_paths.py
"""Tests for path handling utilities."""
import pytest
from pathlib import Path
from api.core.paths import normalize_data_path, IS_DOCKER

def test_normalize_bare_filename():
    """Test normalizing bare filename."""
    result = normalize_data_path("test.csv")
    assert result.name == "test.csv"
    assert "uploads" in str(result)

def test_normalize_relative_path():
    """Test normalizing relative path."""
    result = normalize_data_path("data/uploads/test.csv")
    assert result.name == "test.csv"

def test_normalize_with_prefix():
    """Test normalizing path with local:// prefix."""
    result = normalize_data_path("local://data/uploads/test.csv")
    assert result.name == "test.csv"
    assert "local://" not in str(result)

def test_security_validation():
    """Test that paths outside data dir are rejected."""
    with pytest.raises(ValueError, match="outside allowed"):
        normalize_data_path("/etc/passwd")

# tests/core/test_data.py
# tests/core/test_config.py
# tests/core/test_security.py
```

---

### Task 6.3: Integration Tests for API Endpoints

**Implementation**:
```python
# tests/api/test_endpoints.py
"""Integration tests for TimesFM API endpoints."""
import pytest
from fastapi.testclient import TestClient

def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "status" in response.json()

def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "models" in data

def test_model_status_requires_auth(client):
    """Test that status endpoint requires authentication."""
    response = client.get("/api/v1/timesfm20/status")
    assert response.status_code == 403  # Forbidden

def test_model_status_with_auth(client, auth_headers):
    """Test status endpoint with authentication."""
    response = client.get("/api/v1/timesfm20/status", headers=auth_headers)
    assert response.status_code == 200
    assert "model_status" in response.json()

def test_model_initialization(client, auth_headers):
    """Test model initialization endpoint."""
    # This would use mocked model for speed
    payload = {
        "backend": "cpu",
        "context_len": 64,
        "horizon_len": 24
    }
    response = client.post(
        "/api/v1/timesfm20/initialization",
        headers=auth_headers,
        json=payload
    )
    # May fail if model already initialized, that's ok
    assert response.status_code in [200, 400]

def test_inference_with_missing_data(client, auth_headers):
    """Test inference with non-existent file."""
    payload = {
        "data_source_url_or_path": "nonexistent.csv",
        "data_definition": {"value": "target"},
        "parameters": {}
    }
    response = client.post(
        "/api/v1/timesfm20/inference",
        headers=auth_headers,
        json=payload
    )
    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()

# More tests...
```

---

### Task 6.4: Path Handling Tests

**Implementation**:
```python
# tests/integration/test_path_handling.py
"""Integration tests for path handling across environments."""
import pytest
import os
from unittest.mock import patch

def test_venv_path_resolution():
    """Test path resolution in venv environment."""
    with patch('api.core.paths.IS_DOCKER', False):
        from api.core.paths import normalize_data_path
        result = normalize_data_path("test.csv")
        assert not str(result).startswith('/app')

def test_docker_path_resolution():
    """Test path resolution in Docker environment."""
    with patch('api.core.paths.IS_DOCKER', True):
        from api.core.paths import normalize_data_path
        result = normalize_data_path("test.csv")
        assert str(result).startswith('/app')

# More tests...
```

---

## Phase 7: Error Handling Improvements (Week 3, Days 1-2)

**Goal**: Implement proper error handling hierarchy
**Effort**: 1-2 days
**Priority**: 🟢 MEDIUM

### Task 7.1: Custom Exception Hierarchy

**Implementation**:
```python
# api/core/exceptions.py
"""Custom exception hierarchy for Sapheneia API."""

class SapheneiaException(Exception):
    """Base exception for all Sapheneia errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "SAPHENEIA_ERROR",
        details: dict = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class DataError(SapheneiaException):
    """Data-related errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="DATA_ERROR", **kwargs)


class DataFetchError(DataError):
    """Failed to fetch data from source."""
    pass


class DataValidationError(DataError):
    """Data validation failed."""
    pass


class ModelError(SapheneiaException):
    """Model-related errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="MODEL_ERROR", **kwargs)


class ModelNotInitializedError(ModelError):
    """Model not initialized."""
    pass


class ModelInitializationError(ModelError):
    """Model initialization failed."""
    pass


class InferenceError(ModelError):
    """Inference operation failed."""
    pass


class ConfigurationError(SapheneiaException):
    """Configuration errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="CONFIG_ERROR", **kwargs)


class SecurityError(SapheneiaException):
    """Security-related errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="SECURITY_ERROR", **kwargs)
```

---

### Task 7.2: Error Handler Middleware

**Implementation**:
```python
# api/main.py
from api.core.exceptions import SapheneiaException
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(SapheneiaException)
async def sapheneia_exception_handler(request: Request, exc: SapheneiaException):
    """Handle Sapheneia exceptions with structured responses."""
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception("Unexpected error occurred")
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please contact support."
        }
    )
```

---

## Phase 8: Performance Optimizations (Week 3, Days 3-5)

**Goal**: Optimize async operations and response handling
**Effort**: 2-3 days
**Priority**: 🟢 MEDIUM

### Task 8.1: Async Inference Execution

**Implementation**:
```python
# api/models/timesfm20/routes/endpoints.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Thread pool for CPU-bound operations
executor = ThreadPoolExecutor(max_workers=2)

@router.post("/inference")
async def inference_endpoint(
    input_data: InferenceInput,
    api_key: str = Depends(get_api_key)
):
    """Run inference asynchronously."""

    # ... validation code ...

    # Run CPU-bound inference in thread pool
    loop = asyncio.get_event_loop()

    results = await loop.run_in_executor(
        executor,
        _run_inference_sync,  # Synchronous function
        target_inputs,
        covariates,
        parameters
    )

    return results

def _run_inference_sync(target_inputs, covariates, parameters):
    """Synchronous inference function for thread pool."""
    # ... actual inference code ...
    return results
```

---

### Task 8.2: Response Compression

**Implementation**:
```python
# api/main.py
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

---

## Implementation Timeline

### Week 1: Critical Fixes ✅ COMPLETED
- **Days 1-2**: ✅ Security hardening (Phase 1: Tasks 1.1-1.4)
- **Days 3-4**: ✅ Path handling standardization (Phase 2: Tasks 2.1-2.3)
- **Days 5-7**: ✅ Remove src/ dependency (Phase 3: Tasks 3.1-3.4 + Addendum)

### Week 2: Architecture & API Improvements
- **Days 1-3**: ✅ State management (Phase 4: Tasks 4.1-4.2, Task 4.3 deferred)
- **Days 4-5**: ⏸️ API endpoint improvements (Phase 5: Tasks 5.1-5.5) - NEXT
- **Days 6-7**: ⏸️ Testing infrastructure (Phase 6: Tasks 6.1-6.4)

### Week 3: Polish & Optimization
- **Days 1-2**: ⏸️ Error handling (Phase 7: Tasks 7.1-7.2)
- **Days 3-5**: ⏸️ Performance optimization (Phase 8: Tasks 8.1-8.2)
- **Days 6-7**: ⏸️ Final testing and documentation

---

## Success Criteria

### Phase 1 (Security) ✅
- ✅ No default API keys in production
- ✅ CORS properly configured
- ✅ Rate limiting active
- ✅ File uploads validated

### Phase 2 (Path Handling) ✅
- ✅ Single path utility module
- ✅ Works identically in venv and Docker
- ✅ All paths use utility functions
- ✅ No path-related errors

### Phase 3 (Architecture) ✅
- ✅ No sys.path manipulation
- ✅ All imports use proper modules
- ✅ src/ directory removed completely
- ✅ Clean module structure

### Phase 4 (State Management) ✅
- ✅ Limitations documented
- ✅ Thread safety added
- ✅ Clear warnings in logs
- ⏭️ Redis backend deferred

### Phase 5 (API Improvements) ⏸️
- ⏸️ Comprehensive input validation
- ⏸️ Standardized response formats
- ⏸️ Request size limits enforced
- ⏸️ Response metadata included
- ⏸️ Pagination support ready

### Phase 6 (Testing) ⏸️
- ⏸️ 60%+ code coverage
- ⏸️ All critical paths tested
- ⏸️ CI/CD pipeline ready
- ⏸️ Path handling tested

### Phase 7 (Error Handling) ⏸️
- ⏸️ Custom exception hierarchy
- ⏸️ Structured error responses
- ⏸️ Better error messages

### Phase 8 (Performance) ⏸️
- ⏸️ Async operations
- ⏸️ Response compression
- ⏸️ No blocking calls

---

## Deferred Items (Future Phases)

### Not Included in 3-Week Plan
- Redis state backend (requires infrastructure)
- Architecture diagrams (nice-to-have)
- Prometheus metrics (production monitoring)
- MLflow integration (planned separately)
- Multi-model orchestration (future feature)
- Advanced security (OAuth2, JWT)
- Batch processing endpoints

---

## Risk Mitigation

### High-Risk Changes
1. **Path handling refactor** - Risk: Breaking existing functionality
   - Mitigation: Comprehensive testing, gradual rollout

2. **src/ migration** - Risk: Breaking imports
   - Mitigation: Keep src/ as backup, thorough testing

3. **State management changes** - Risk: Breaking model lifecycle
   - Mitigation: Start with documentation, add threading gradually

### Testing Strategy
- Test each phase independently
- Keep main branch stable
- Use feature branches
- Manual testing after each phase
- Automated tests before merge

---

**End of Remediation Plan**

*This plan prioritizes security and critical issues first, followed by architectural improvements and testing. Each phase builds on the previous one, ensuring stable progress toward production readiness.*
