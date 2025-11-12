# Trading Strategies Application - Implementation Plan

**Project**: Sapheneia Trading Strategies Module
**Branch**: `trading_strategies`
**Created**: 2025-11-12
**Status**: Awaiting Approval

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Project Context Analysis](#project-context-analysis)
3. [Architecture Design](#architecture-design)
4. [Implementation Phases](#implementation-phases)
5. [File Structure & Components](#file-structure--components)
6. [API Design](#api-design)
7. [Schema Design](#schema-design)
8. [Security & Authentication](#security--authentication)
9. [Configuration Management](#configuration-management)
10. [Testing Strategy](#testing-strategy)
11. [Deployment Strategy](#deployment-strategy)
12. [Dependencies](#dependencies)
13. [Migration from Sample Code](#migration-from-sample-code)
14. [Timeline & Milestones](#timeline--milestones)
15. [Risk Assessment](#risk-assessment)
16. [Success Criteria](#success-criteria)

---

## 1. Executive Summary

### Objective
Develop a production-ready FastAPI application for executing trading strategies that integrates seamlessly with the existing Sapheneia forecasting platform.

### Key Requirements
- **Stateless execution**: All state (positions, capital) provided by orchestrator
- **Three strategy types**: Threshold, Return, and Quantile-based strategies
- **Long-only positions**: No short selling allowed
- **OHLC data support**: Open, High, Low, Close historical price data
- **Scalable architecture**: Handle concurrent requests efficiently
- **Dual deployment**: Support both `.venv` and Docker environments

### Deliverables
1. FastAPI application with `/execute` endpoint
2. Complete Pydantic schema validation system
3. API key authentication layer
4. Comprehensive test suite (unit + integration)
5. Docker configuration
6. Updated setup.sh script
7. Documentation and usage examples

---

## 2. Project Context Analysis

### 2.1 Existing Patterns Identified

From analyzing the existing `api/` module, the following patterns will be followed:

| Component | Existing Pattern | Application to Trading Module |
|-----------|-----------------|-------------------------------|
| **Config Management** | Pydantic Settings with `.env` support | `trading/core/config.py` with trading-specific settings |
| **Authentication** | HTTPBearer with API key validation | `trading/core/security.py` mirroring api/core/security.py |
| **Exception Handling** | Custom exception hierarchy | Create `trading/core/exceptions.py` with trading-specific errors |
| **Rate Limiting** | slowapi with per-endpoint limits | Apply to `/execute` endpoint (10/minute default) |
| **Router Structure** | Separate routes module with FastAPI router | `trading/routes/endpoints.py` with single `/execute` endpoint |
| **Schema Validation** | Pydantic models for request/response | `trading/schemas/schema.py` with comprehensive validation |
| **Logging** | Python logging module with structured output | Configure in config.py with request IDs |
| **Testing** | pytest with fixtures and coverage | Mirror structure in `trading/tests/` |

### 2.2 Technology Stack Alignment

**Confirmed Technologies**:
- Python 3.11+
- FastAPI 0.109.0+
- Pydantic 2.5.0+
- uvicorn (ASGI server)
- pytest (testing)
- uv (package management)
- Docker & Docker Compose

**Key Dependencies to Add**:
- numpy (already in project) - for calculations
- No additional external dependencies required

---

## 3. Architecture Design

### 3.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Orchestrator Application                    │
│                     (Future Development)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP POST /api/v1/trading/execute
                             │ Authorization: Bearer <API_KEY>
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Trading Strategies API                        │
│                      (FastAPI Application)                       │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Security   │  │ Rate Limiter │  │  Exception   │          │
│  │  Middleware  │  │              │  │   Handler    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │            /execute Endpoint (POST)                       │  │
│  │  - Validates request schema                               │  │
│  │  - Routes to appropriate strategy                         │  │
│  │  - Returns execution result                               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                             │                                     │
│                             ▼                                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │          TradingStrategy Service                          │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │  │
│  │  │  Threshold  │ │   Return    │ │  Quantile   │        │  │
│  │  │  Strategy   │ │  Strategy   │ │  Strategy   │        │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Application Flow

1. **Request Reception**: Client sends POST request to `/execute` with JSON payload
2. **Authentication**: API key validated via `get_api_key()` dependency
3. **Rate Limiting**: Request checked against rate limit (default: 10/minute)
4. **Schema Validation**: Pydantic validates request parameters
5. **Strategy Selection**: Route to appropriate strategy based on `strategy_type`
6. **Strategy Execution**: Stateless strategy execution with capital management
7. **Response Formation**: Return structured JSON with execution results
8. **Error Handling**: Any exceptions caught and returned with appropriate status codes

### 3.3 Design Principles

- **Stateless**: No session state; all context provided in each request
- **Idempotent**: Same inputs produce same outputs (no side effects)
- **Fast**: Target <100ms response time for typical requests
- **Scalable**: Can handle concurrent requests (stateless design enables horizontal scaling)
- **Testable**: Pure functions enable comprehensive unit testing
- **Extensible**: Easy to add new strategy types

---

## 4. Implementation Phases

### Phase 1: Core Infrastructure (Priority: Critical)
- [ ] Create directory structure
- [ ] Implement `core/config.py` (trading-specific settings)
- [ ] Implement `core/security.py` (API key authentication)
- [ ] Implement `core/exceptions.py` (custom exceptions)
- [ ] Set up logging configuration

### Phase 2: Business Logic (Priority: Critical)
- [ ] Migrate `TradingStrategy` class from sample code to `services/strategy.py`
- [ ] Create helper modules for calculations (if needed for organization)
- [ ] Implement parameter validation logic
- [ ] Add comprehensive docstrings and type hints

### Phase 3: API Layer (Priority: Critical)
- [ ] Design Pydantic schemas in `schemas/schema.py`
- [ ] Create comprehensive request/response models for all three strategies
- [ ] Implement `/execute` endpoint in `routes/endpoints.py`
- [ ] Add rate limiting decorators
- [ ] Implement error handling

### Phase 4: FastAPI Application (Priority: Critical)
- [ ] Create `main.py` with FastAPI app instance
- [ ] Configure middleware (CORS, GZip, request size limiting)
- [ ] Register exception handlers
- [ ] Add health check endpoints (`/health`, `/`)
- [ ] Include trading router with prefix

### Phase 5: Testing (Priority: High)
- [ ] Unit tests for each strategy type
- [ ] Unit tests for helper methods (ATR, returns, thresholds)
- [ ] Integration tests for `/execute` endpoint
- [ ] Edge case tests (insufficient cash, no position, stopped strategies)
- [ ] Authentication failure tests
- [ ] Invalid parameter tests
- [ ] Achieve >70% code coverage

### Phase 6: Deployment Configuration (Priority: High)
- [ ] Create `Dockerfile.trading` for trading service
- [ ] Update `docker-compose.yml` to include trading service
- [ ] Update `setup.sh` to support trading module
- [ ] Create `.env.template` entries for trading configuration
- [ ] Test both `.venv` and Docker deployment modes

### Phase 7: Documentation (Priority: Medium)
- [ ] Create `trading/README.md` with API documentation
- [ ] Document all environment variables
- [ ] Create usage examples with `curl` commands
- [ ] Update root `README.md` to include trading module
- [ ] Update `CLAUDE.md` with implementation progress

### Phase 8: Integration & Polish (Priority: Medium)
- [ ] Integration with main API (optional: unified endpoint)
- [ ] Performance testing and optimization
- [ ] Security audit
- [ ] Final testing with various scenarios
- [ ] Code review and refinement

---

## 5. File Structure & Components

### 5.1 Complete Directory Structure

```
sapheneia/
├── trading/                             # Trading strategies application
│   ├── __init__.py                      # Package initialization
│   │
│   ├── main.py                          # FastAPI app instance
│   │   └── Functions:
│   │       ├── create_app() -> FastAPI
│   │       ├── @app.on_event("startup")
│   │       └── @app.on_event("shutdown")
│   │
│   ├── core/                            # Core infrastructure
│   │   ├── __init__.py
│   │   │
│   │   ├── config.py                    # Configuration management
│   │   │   └── Classes:
│   │   │       └── TradingSettings(BaseSettings)
│   │   │           ├── TRADING_API_KEY: str
│   │   │           ├── TRADING_API_HOST: str
│   │   │           ├── TRADING_API_PORT: int
│   │   │           ├── LOG_LEVEL: str
│   │   │           ├── RATE_LIMIT_ENABLED: bool
│   │   │           ├── RATE_LIMIT_PER_MINUTE: int
│   │   │           └── CORS settings
│   │   │
│   │   ├── security.py                  # Authentication
│   │   │   └── Functions:
│   │   │       ├── get_api_key() -> str
│   │   │       └── security_scheme: HTTPBearer
│   │   │
│   │   ├── exceptions.py                # Custom exceptions
│   │   │   └── Classes:
│   │   │       ├── TradingException(Exception)
│   │   │       ├── InvalidStrategyError(TradingException)
│   │   │       ├── InsufficientCapitalError(TradingException)
│   │   │       ├── InvalidParametersError(TradingException)
│   │   │       └── StrategyStoppedError(TradingException)
│   │   │
│   │   └── rate_limit.py                # Rate limiting setup
│   │       └── Functions:
│   │           ├── setup_rate_limiter() -> Limiter
│   │           └── get_rate_limit(endpoint_type: str) -> str
│   │
│   ├── routes/                          # API endpoints
│   │   ├── __init__.py
│   │   │
│   │   └── endpoints.py                 # Trading endpoints
│   │       └── Endpoints:
│   │           ├── POST /execute
│   │           ├── GET /strategies (list available strategies)
│   │           └── GET /status
│   │
│   ├── schemas/                         # Pydantic models
│   │   ├── __init__.py
│   │   │
│   │   ├── base.py                      # Base schemas
│   │   │   └── Classes:
│   │   │       ├── BaseStrategyRequest
│   │   │       ├── BaseStrategyResponse
│   │   │       └── ErrorResponse
│   │   │
│   │   └── schema.py                    # Strategy schemas
│   │       └── Classes:
│   │           ├── ThresholdStrategyRequest(BaseStrategyRequest)
│   │           ├── ReturnStrategyRequest(BaseStrategyRequest)
│   │           ├── QuantileStrategyRequest(BaseStrategyRequest)
│   │           ├── StrategyRequest (Union discriminator)
│   │           ├── StrategyResponse
│   │           └── StrategyListResponse
│   │
│   ├── services/                        # Business logic
│   │   ├── __init__.py
│   │   │
│   │   └── strategy.py                  # TradingStrategy class (migrated from sample)
│   │       └── Classes:
│   │           ├── StrategyType(Enum)
│   │           ├── ThresholdType(Enum)
│   │           ├── PositionSizing(Enum)
│   │           ├── WhichHistory(Enum)
│   │           └── TradingStrategy
│   │               ├── execute_trading_signal()
│   │               ├── generate_trading_signal()
│   │               ├── calculate_threshold_signal()
│   │               ├── calculate_return_signal()
│   │               ├── calculate_quantile_signal()
│   │               └── Helper methods (_calculate_atr, etc.)
│   │
│   ├── tests/                           # Test suite
│   │   ├── __init__.py
│   │   ├── conftest.py                  # Pytest fixtures
│   │   │
│   │   ├── unit/                        # Unit tests
│   │   │   ├── test_strategy_threshold.py
│   │   │   ├── test_strategy_return.py
│   │   │   ├── test_strategy_quantile.py
│   │   │   ├── test_helpers.py
│   │   │   └── test_config.py
│   │   │
│   │   └── integration/                 # Integration tests
│   │       ├── test_execute_endpoint.py
│   │       ├── test_authentication.py
│   │       └── test_rate_limiting.py
│   │
│   ├── sample/                          # Reference code (existing)
│   │   ├── sample-code.py               # Original implementation
│   │   └── example-usage.py             # Usage examples
│   │
│   └── README.md                        # Trading module documentation
│
├── Dockerfile.trading                   # Docker configuration for trading service
├── docker-compose.yml                   # Updated with trading service
├── setup.sh                             # Updated with trading support
├── .env.template                        # Updated with trading variables
└── CLAUDE.md                            # Development progress tracking
```

### 5.2 Key Files Detailed Design

#### `trading/main.py`

```python
"""
Trading Strategies FastAPI Application

Main entry point for the trading strategies service.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging

from trading.core.config import settings
from trading.core.exceptions import TradingException
from trading.core.rate_limit import setup_rate_limiter, limiter
from trading.routes import endpoints

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title="Sapheneia Trading Strategies API",
        description="Trading strategy execution service for long-only positions",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Middleware configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Rate limiting
    if settings.RATE_LIMIT_ENABLED:
        app.state.limiter = limiter

    # Exception handlers
    @app.exception_handler(TradingException)
    async def trading_exception_handler(request: Request, exc: TradingException):
        return JSONResponse(
            status_code=400,
            content={"error": exc.__class__.__name__, "message": str(exc)}
        )

    # Include routers
    app.include_router(
        endpoints.router,
        prefix="/api/v1/trading",
        tags=["trading"]
    )

    # Health check endpoints
    @app.get("/", tags=["health"])
    async def root():
        return {"status": "ok", "service": "trading-strategies", "version": "1.0.0"}

    @app.get("/health", tags=["health"])
    async def health_check():
        return {
            "status": "healthy",
            "service": "trading-strategies",
            "version": "1.0.0",
            "available_strategies": ["threshold", "return", "quantile"]
        }

    @app.on_event("startup")
    async def startup_event():
        logger.info("Trading Strategies API starting up...")
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        logger.info(f"Rate limiting: {'enabled' if settings.RATE_LIMIT_ENABLED else 'disabled'}")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Trading Strategies API shutting down...")

    return app

app = create_app()
```

#### `trading/core/config.py`

```python
"""
Configuration management for Trading Strategies API
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List
import os


class TradingSettings(BaseSettings):
    """Trading API configuration settings"""

    # API Configuration
    TRADING_API_KEY: str = Field(..., min_length=32, description="API key for authentication")
    TRADING_API_HOST: str = Field(default="0.0.0.0", description="API host")
    TRADING_API_PORT: int = Field(default=8001, description="API port")
    ENVIRONMENT: str = Field(default="development", description="Environment (development/staging/production)")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # CORS Configuration
    CORS_ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:8080", "http://localhost:3000"],
        description="Allowed CORS origins"
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting")
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="Default rate limit per minute")
    RATE_LIMIT_EXECUTE_PER_MINUTE: int = Field(default=10, description="Rate limit for execute endpoint")

    # Trading Strategy Defaults
    DEFAULT_MIN_HISTORY_LENGTH: int = Field(default=2, description="Minimum history length required")
    DEFAULT_EXECUTION_SIZE: float = Field(default=1.0, description="Default execution size")

    @validator("TRADING_API_KEY")
    def validate_api_key(cls, v, values):
        """Ensure API key is sufficiently strong in production"""
        env = values.get("ENVIRONMENT", "development")
        if env == "production" and len(v) < 32:
            raise ValueError("API key must be at least 32 characters in production")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = TradingSettings()
```

#### `trading/schemas/schema.py`

```python
"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, Field, validator
from typing import Literal, Dict, List, Optional, Union
from enum import Enum
import numpy as np


class StrategyTypeEnum(str, Enum):
    THRESHOLD = "threshold"
    RETURN = "return"
    QUANTILE = "quantile"


# Base Request Schema
class BaseStrategyRequest(BaseModel):
    """Base schema for all strategy requests"""
    strategy_type: StrategyTypeEnum
    forecast_price: float = Field(..., gt=0, description="Forecasted price")
    current_price: float = Field(..., gt=0, description="Current market price")
    current_position: float = Field(..., ge=0, description="Current position size")
    available_cash: float = Field(..., ge=0, description="Available cash")
    initial_capital: float = Field(..., gt=0, description="Initial capital")


# Threshold Strategy Schema
class ThresholdStrategyRequest(BaseStrategyRequest):
    """Schema for threshold-based strategy"""
    strategy_type: Literal["threshold"] = "threshold"
    threshold_type: Literal["absolute", "percentage", "std_dev", "atr"]
    threshold_value: float = Field(default=0.0, ge=0)
    execution_size: float = Field(default=1.0, gt=0)

    # Conditional fields for std_dev and atr
    which_history: Optional[Literal["open", "high", "low", "close"]] = "close"
    window_history: Optional[int] = Field(default=20, gt=0)
    min_history_length: Optional[int] = Field(default=2, gt=0)

    # OHLC data (required for atr, optional for std_dev)
    open_history: Optional[List[float]] = None
    high_history: Optional[List[float]] = None
    low_history: Optional[List[float]] = None
    close_history: Optional[List[float]] = None


# Return Strategy Schema
class ReturnStrategyRequest(BaseStrategyRequest):
    """Schema for return-based strategy"""
    strategy_type: Literal["return"] = "return"
    position_sizing: Literal["fixed", "proportional", "normalized"]
    threshold_value: float = Field(..., ge=0, description="Return threshold (e.g., 0.05 for 5%)")
    execution_size: float = Field(default=1.0, gt=0)
    max_position_size: Optional[float] = Field(default=None, gt=0)
    min_position_size: Optional[float] = Field(default=None, gt=0)

    # Conditional for normalized sizing
    which_history: Optional[Literal["open", "high", "low", "close"]] = "close"
    window_history: Optional[int] = Field(default=20, gt=0)
    min_history_length: Optional[int] = Field(default=2, gt=0)
    open_history: Optional[List[float]] = None
    high_history: Optional[List[float]] = None
    low_history: Optional[List[float]] = None
    close_history: Optional[List[float]] = None


# Quantile Strategy Schema
class QuantileSignalConfig(BaseModel):
    """Configuration for a single quantile signal"""
    range: List[float] = Field(..., min_items=2, max_items=2)
    signal: Literal["buy", "sell", "hold"]
    multiplier: float = Field(..., ge=0, le=1)


class QuantileStrategyRequest(BaseStrategyRequest):
    """Schema for quantile-based strategy"""
    strategy_type: Literal["quantile"] = "quantile"
    which_history: Literal["open", "high", "low", "close"]
    window_history: int = Field(..., gt=0)
    quantile_signals: Dict[int, QuantileSignalConfig]
    position_sizing: Optional[Literal["fixed", "normalized"]] = "fixed"
    execution_size: float = Field(default=1.0, gt=0)
    max_position_size: Optional[float] = Field(default=None, gt=0)
    min_position_size: Optional[float] = Field(default=None, gt=0)
    min_history_length: Optional[int] = Field(default=2, gt=0)

    # OHLC data (required)
    open_history: List[float]
    high_history: List[float]
    low_history: List[float]
    close_history: List[float]


# Union type for request routing
StrategyRequest = Union[ThresholdStrategyRequest, ReturnStrategyRequest, QuantileStrategyRequest]


# Response Schema
class StrategyResponse(BaseModel):
    """Response schema for strategy execution"""
    action: Literal["buy", "sell", "hold"]
    size: float = Field(..., ge=0)
    value: float = Field(..., ge=0)
    reason: str
    available_cash: float = Field(..., ge=0)
    position_after: float = Field(..., ge=0)
    stopped: bool

    class Config:
        json_schema_extra = {
            "example": {
                "action": "buy",
                "size": 100.0,
                "value": 10000.0,
                "reason": "Forecast 105.00 > Price 100.00, magnitude 5.0000 > threshold 0.0000",
                "available_cash": 90000.0,
                "position_after": 100.0,
                "stopped": False
            }
        }
```

---

## 6. API Design

### 6.1 Endpoint Specification

#### POST `/api/v1/trading/execute`

**Description**: Execute a trading strategy and return the recommended action.

**Authentication**: Required (Bearer token)

**Rate Limit**: 10 requests/minute (configurable)

**Request Headers**:
```
Authorization: Bearer <TRADING_API_KEY>
Content-Type: application/json
```

**Request Body** (Threshold Strategy Example):
```json
{
  "strategy_type": "threshold",
  "forecast_price": 105.0,
  "current_price": 100.0,
  "current_position": 0.0,
  "available_cash": 100000.0,
  "initial_capital": 100000.0,
  "threshold_type": "absolute",
  "threshold_value": 0.0,
  "execution_size": 100.0
}
```

**Response** (200 OK):
```json
{
  "action": "buy",
  "size": 100.0,
  "value": 10000.0,
  "reason": "Forecast 105.00 > Price 100.00, magnitude 5.0000 > threshold 0.0000",
  "available_cash": 90000.0,
  "position_after": 100.0,
  "stopped": false
}
```

**Error Responses**:

- **400 Bad Request**: Invalid parameters
```json
{
  "error": "InvalidParametersError",
  "message": "threshold_value must be non-negative"
}
```

- **401 Unauthorized**: Invalid or missing API key
```json
{
  "error": "UnauthorizedError",
  "message": "Invalid API key"
}
```

- **429 Too Many Requests**: Rate limit exceeded
```json
{
  "error": "RateLimitExceededError",
  "message": "Rate limit exceeded. Try again later."
}
```

- **500 Internal Server Error**: Server error
```json
{
  "error": "InternalServerError",
  "message": "An unexpected error occurred"
}
```

#### GET `/api/v1/trading/strategies`

**Description**: List available strategy types and their parameters.

**Authentication**: Optional

**Response** (200 OK):
```json
{
  "strategies": [
    {
      "type": "threshold",
      "description": "Threshold-based strategy with configurable threshold types",
      "parameters": {
        "required": ["forecast_price", "current_price", "threshold_type", "threshold_value"],
        "optional": ["execution_size", "which_history", "window_history"]
      }
    },
    {
      "type": "return",
      "description": "Return-based strategy with position sizing options",
      "parameters": {
        "required": ["forecast_price", "current_price", "position_sizing", "threshold_value"],
        "optional": ["execution_size", "max_position_size", "min_position_size"]
      }
    },
    {
      "type": "quantile",
      "description": "Quantile-based strategy using empirical quantiles",
      "parameters": {
        "required": ["forecast_price", "current_price", "quantile_signals", "window_history", "open_history", "high_history", "low_history", "close_history"],
        "optional": ["position_sizing", "execution_size"]
      }
    }
  ]
}
```

#### GET `/health`

**Description**: Health check endpoint.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "service": "trading-strategies",
  "version": "1.0.0",
  "available_strategies": ["threshold", "return", "quantile"]
}
```

---

## 7. Schema Design

### 7.1 Schema Validation Strategy

**Discriminated Union Pattern**: Use Pydantic's discriminator feature to route requests based on `strategy_type`.

**Benefits**:
- Automatic request routing
- Strategy-specific validation
- Clear OpenAPI documentation
- Type safety

### 7.2 Validation Rules

| Field | Validation | Rationale |
|-------|-----------|-----------|
| `forecast_price` | > 0 | Prices must be positive |
| `current_price` | > 0 | Prices must be positive |
| `current_position` | >= 0 | Long-only (no negative positions) |
| `available_cash` | >= 0 | Cannot have negative cash |
| `initial_capital` | > 0 | Must have starting capital |
| `execution_size` | > 0 | Must trade at least some amount |
| `threshold_value` | >= 0 | Thresholds are non-negative |
| `window_history` | > 0 | Window must be at least 1 |
| `min_history_length` | > 0 | Need at least 1 historical point |
| OHLC arrays | Same length | All OHLC arrays must match in length |

### 7.3 Custom Validators

Additional validators will be implemented for:
- Ensuring OHLC data is provided when required (atr, std_dev)
- Validating quantile signal ranges don't overlap
- Checking history array lengths match
- Validating position size constraints (min < max)

---

## 8. Security & Authentication

### 8.1 Authentication Mechanism

**Method**: HTTP Bearer token authentication

**Implementation**:
```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security, HTTPException

security_scheme = HTTPBearer()

async def get_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme)
) -> str:
    """Validate API key from Authorization header"""
    if credentials.credentials != settings.TRADING_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return credentials.credentials
```

**Usage**:
```python
@router.post("/execute", dependencies=[Depends(get_api_key)])
async def execute_strategy(request: StrategyRequest):
    ...
```

### 8.2 Security Best Practices

- [ ] API keys stored in environment variables (never hardcoded)
- [ ] Minimum 32-character API keys in production
- [ ] HTTPS only in production (enforced via reverse proxy)
- [ ] Rate limiting to prevent abuse
- [ ] Input validation via Pydantic (prevent injection attacks)
- [ ] No sensitive data in logs (no API keys, trade amounts)
- [ ] CORS restricted to known origins
- [ ] Request size limiting (10MB max)

### 8.3 Rate Limiting Configuration

| Endpoint Type | Default Limit | Configurable |
|--------------|---------------|--------------|
| Health checks | 30/minute | Yes |
| Strategy list | 30/minute | Yes |
| Execute | 10/minute | Yes |

---

## 9. Configuration Management

### 9.1 Environment Variables

Add to `.env.template`:

```bash
# ============================================================================
# Trading Strategies API Configuration
# ============================================================================

# API Authentication (REQUIRED)
TRADING_API_KEY=<generate_secure_key_min_32_chars>

# API Server Configuration
TRADING_API_HOST=0.0.0.0
TRADING_API_PORT=8001
ENVIRONMENT=development  # development, staging, production
LOG_LEVEL=INFO           # DEBUG, INFO, WARNING, ERROR

# CORS Configuration
CORS_ALLOWED_ORIGINS=http://localhost:8080,http://localhost:3000
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST
CORS_ALLOW_HEADERS=*

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_EXECUTE_PER_MINUTE=10

# Trading Strategy Defaults
DEFAULT_MIN_HISTORY_LENGTH=2
DEFAULT_EXECUTION_SIZE=1.0
```

### 9.2 Configuration Loading

Configuration loaded via Pydantic Settings:
1. Environment variables take precedence
2. `.env` file as fallback
3. Default values if not specified
4. Validation on application startup

---

## 10. Testing Strategy

### 10.1 Test Structure

```
trading/tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_strategy_threshold.py
│   ├── test_strategy_return.py
│   ├── test_strategy_quantile.py
│   ├── test_helpers.py
│   └── test_config.py
└── integration/
    ├── test_execute_endpoint.py
    ├── test_authentication.py
    └── test_rate_limiting.py
```

### 10.2 Test Coverage Goals

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| Strategy logic | >90% | Critical |
| API endpoints | >85% | Critical |
| Schemas | >80% | High |
| Config/Security | >70% | High |
| Overall | >70% | Required |

### 10.3 Test Categories

#### Unit Tests (trading/tests/unit/)

**test_strategy_threshold.py**:
- [ ] Test absolute threshold (buy signal)
- [ ] Test absolute threshold (sell signal)
- [ ] Test absolute threshold (hold signal)
- [ ] Test percentage threshold
- [ ] Test std_dev threshold
- [ ] Test ATR threshold
- [ ] Test insufficient cash scenario
- [ ] Test no position to sell scenario
- [ ] Test strategy stopped condition

**test_strategy_return.py**:
- [ ] Test fixed position sizing
- [ ] Test proportional position sizing
- [ ] Test normalized position sizing
- [ ] Test return threshold (buy)
- [ ] Test return threshold (sell)
- [ ] Test return within threshold (hold)
- [ ] Test max/min position size constraints
- [ ] Test insufficient history fallback

**test_strategy_quantile.py**:
- [ ] Test buy signal from quantile range
- [ ] Test sell signal from quantile range
- [ ] Test hold when no range matches
- [ ] Test multiplier application
- [ ] Test normalized position sizing
- [ ] Test insufficient history error
- [ ] Test percentile calculation accuracy

**test_helpers.py**:
- [ ] Test ATR calculation
- [ ] Test returns calculation
- [ ] Test threshold calculation (all types)
- [ ] Test history array getter
- [ ] Test portfolio value calculation
- [ ] Test portfolio return calculation

**test_config.py**:
- [ ] Test config loading from environment
- [ ] Test API key validation (production mode)
- [ ] Test default values
- [ ] Test invalid configurations

#### Integration Tests (trading/tests/integration/)

**test_execute_endpoint.py**:
- [ ] Test threshold strategy execution (valid)
- [ ] Test return strategy execution (valid)
- [ ] Test quantile strategy execution (valid)
- [ ] Test invalid strategy type
- [ ] Test missing required parameters
- [ ] Test invalid parameter types
- [ ] Test negative prices/positions
- [ ] Test response schema validation

**test_authentication.py**:
- [ ] Test valid API key
- [ ] Test invalid API key
- [ ] Test missing API key
- [ ] Test malformed Authorization header

**test_rate_limiting.py**:
- [ ] Test rate limit enforcement
- [ ] Test rate limit reset
- [ ] Test different limits for different endpoints

### 10.4 Test Fixtures (conftest.py)

```python
@pytest.fixture
def sample_ohlc_data():
    """Generate sample OHLC data for testing"""
    np.random.seed(42)
    return {
        'open_history': np.random.uniform(95, 105, 30).tolist(),
        'high_history': np.random.uniform(100, 110, 30).tolist(),
        'low_history': np.random.uniform(90, 100, 30).tolist(),
        'close_history': np.random.uniform(95, 105, 30).tolist(),
    }

@pytest.fixture
def base_params():
    """Base parameters for strategy testing"""
    return {
        'forecast_price': 105.0,
        'current_price': 100.0,
        'current_position': 0.0,
        'available_cash': 100000.0,
        'initial_capital': 100000.0,
    }

@pytest.fixture
def test_client():
    """FastAPI test client with authentication"""
    from fastapi.testclient import TestClient
    from trading.main import app
    return TestClient(app)

@pytest.fixture
def auth_headers():
    """Authentication headers for testing"""
    return {"Authorization": f"Bearer {settings.TRADING_API_KEY}"}
```

### 10.5 Test Execution

```bash
# Run all tests
uv run pytest trading/tests/ -v

# Run unit tests only
uv run pytest trading/tests/unit/ -v

# Run integration tests only
uv run pytest trading/tests/integration/ -v

# Run with coverage
uv run pytest trading/tests/ --cov=trading --cov-report=html

# Run specific test file
uv run pytest trading/tests/unit/test_strategy_threshold.py -v
```

---

## 11. Deployment Strategy

### 11.1 Local Development (.venv)

**Setup**:
```bash
# Initialize environment
./setup.sh init

# Run trading API
./setup.sh run-venv trading
```

**Direct uvicorn command**:
```bash
# Activate venv
source .venv/bin/activate

# Run server
uvicorn trading.main:app --host 0.0.0.0 --port 8001 --reload
```

### 11.2 Docker Deployment

#### Dockerfile.trading

```dockerfile
# Multi-stage build for trading strategies service
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv pip install --system -r pyproject.toml

# Copy application code
COPY trading/ ./trading/

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run application
CMD ["uvicorn", "trading.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

#### Update docker-compose.yml

```yaml
services:
  # ... existing services (api, ui) ...

  trading:
    build:
      context: .
      dockerfile: Dockerfile.trading
    container_name: sapheneia-trading
    ports:
      - "${TRADING_API_PORT:-8001}:8001"
    volumes:
      - ./trading:/app/trading
      - ./logs:/app/logs
    environment:
      - TRADING_API_KEY=${TRADING_API_KEY}
      - TRADING_API_HOST=0.0.0.0
      - TRADING_API_PORT=8001
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - ENVIRONMENT=${ENVIRONMENT:-development}
    networks:
      - sapheneia-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  sapheneia-network:
    driver: bridge
```

### 11.3 Update setup.sh

Add trading service support:

```bash
# Add to run-venv function
run_trading_venv() {
    log "INFO" "Starting Trading Strategies API (venv mode)..."
    source "$VENV_PATH/bin/activate"
    uvicorn trading.main:app \
        --host "${TRADING_API_HOST:-0.0.0.0}" \
        --port "${TRADING_API_PORT:-8001}" \
        --reload
}

# Add to run-docker function
run_trading_docker() {
    log "INFO" "Starting Trading Strategies API (Docker mode)..."
    docker-compose up trading -d
}

# Update main case statement
case "$1" in
    # ... existing cases ...
    run-venv)
        case "$2" in
            trading) run_trading_venv ;;
            all) run_all_venv ;;
            *) echo "Usage: $0 run-venv [api|ui|trading|all]" ;;
        esac
        ;;
    run-docker)
        case "$2" in
            trading) run_trading_docker ;;
            all) run_all_docker ;;
            *) echo "Usage: $0 run-docker [api|ui|trading|all]" ;;
        esac
        ;;
esac
```

---

## 12. Dependencies

### 12.1 Required Dependencies (Already in Project)

- fastapi>=0.109.0
- uvicorn[standard]>=0.27.0
- pydantic>=2.5.0
- pydantic-settings>=2.1.0
- python-dotenv>=1.0.0
- numpy>=1.24.0
- slowapi>=0.1.9

### 12.2 Dev/Test Dependencies (Already in Project)

- pytest>=7.4.0
- pytest-asyncio>=0.21.0
- pytest-cov>=4.1.0
- httpx>=0.25.0

### 12.3 No Additional Dependencies Required

All necessary dependencies are already present in the project's `pyproject.toml`. No new packages need to be added.

---

## 13. Migration from Sample Code

### 13.1 Migration Checklist

- [ ] Copy `TradingStrategy` class from `sample/sample-code.py` to `services/strategy.py`
- [ ] Copy enum classes (StrategyType, ThresholdType, etc.)
- [ ] Add comprehensive type hints (already mostly present)
- [ ] Add detailed docstrings in Google style
- [ ] Ensure all methods are properly documented
- [ ] Add inline comments for complex calculations
- [ ] Keep sample code as reference (don't delete)

### 13.2 Code Quality Improvements

During migration, apply these improvements:

1. **Type Hints**: Ensure all parameters and returns have type hints
2. **Docstrings**: Add detailed Google-style docstrings
3. **Comments**: Add inline comments for complex logic (ATR, quantile calculations)
4. **Error Messages**: Improve error messages with actionable information
5. **Logging**: Add logging statements at key points
6. **Constants**: Extract magic numbers to named constants if applicable

### 13.3 No Functional Changes

**IMPORTANT**: Do not modify the core logic during migration. The strategy implementations have been provided and should work as-is. Only add documentation, types, and logging.

---

## 14. Timeline & Milestones

### 14.1 Estimated Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Core Infrastructure | 1-2 hours | None |
| Phase 2: Business Logic | 2-3 hours | Phase 1 |
| Phase 3: API Layer | 2-3 hours | Phase 1, 2 |
| Phase 4: FastAPI Application | 1-2 hours | Phase 1, 2, 3 |
| Phase 5: Testing | 3-4 hours | Phase 2, 3, 4 |
| Phase 6: Deployment Config | 1-2 hours | Phase 4 |
| Phase 7: Documentation | 1-2 hours | All phases |
| Phase 8: Integration & Polish | 2-3 hours | All phases |
| **Total** | **13-21 hours** | |

### 14.2 Milestones

**Milestone 1**: Core Foundation Complete
- ✅ Directory structure created
- ✅ Core modules implemented (config, security, exceptions)
- ✅ Basic FastAPI app running

**Milestone 2**: Business Logic Complete
- ✅ TradingStrategy class migrated
- ✅ All three strategies functional
- ✅ Helper methods tested

**Milestone 3**: API Functional
- ✅ /execute endpoint working
- ✅ Schema validation functional
- ✅ Authentication enforced

**Milestone 4**: Testing Complete
- ✅ Unit tests passing (>90% strategy coverage)
- ✅ Integration tests passing (>85% endpoint coverage)
- ✅ Overall coverage >70%

**Milestone 5**: Deployment Ready
- ✅ Docker configuration working
- ✅ setup.sh updated and tested
- ✅ Both .venv and Docker modes functional

**Milestone 6**: Production Ready
- ✅ Documentation complete
- ✅ All tests passing
- ✅ Security audit complete
- ✅ Performance requirements met (<100ms response time)

---

## 15. Risk Assessment

### 15.1 Technical Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Schema validation complexity | Medium | Use Pydantic discriminated unions; comprehensive testing |
| Performance issues with large history arrays | Low | Implement array size limits in validation; use numpy efficiently |
| Concurrent request handling | Low | FastAPI handles this well; stateless design enables parallelization |
| Insufficient test coverage | Medium | Set minimum coverage requirement (70%); automate checks |
| Docker build issues | Low | Follow existing patterns from api/ui; test early |

### 15.2 Integration Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Breaking existing setup.sh | Medium | Test existing services after changes; maintain backward compatibility |
| Port conflicts | Low | Use configurable ports; document port assignments |
| Environment variable conflicts | Low | Use unique prefixes (TRADING_*); document all variables |

### 15.3 Security Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| API key exposure | High | Never commit .env; use .env.template; strong validation |
| Injection attacks | Medium | Pydantic validation; input sanitization |
| DoS via large requests | Medium | Request size limiting; rate limiting; array size validation |
| CORS misconfiguration | Low | Restrictive defaults; document proper CORS setup |

---

## 16. Success Criteria

### 16.1 Functional Requirements

- [x] All three strategy types (threshold, return, quantile) functional
- [ ] Single `/execute` endpoint accepts all strategy types
- [ ] Correct capital management (stateless execution)
- [ ] Long-only enforcement (no negative positions)
- [ ] Proper handling of insufficient capital scenarios
- [ ] Strategy stopped detection

### 16.2 Non-Functional Requirements

- [ ] Response time <100ms for typical requests (tested)
- [ ] Test coverage >70% overall, >90% for strategy logic
- [ ] API documentation auto-generated and accurate (Swagger/ReDoc)
- [ ] Both .venv and Docker deployment modes working
- [ ] Logging properly configured with appropriate levels
- [ ] Security requirements met (authentication, rate limiting, validation)

### 16.3 Documentation Requirements

- [ ] API documentation complete with curl examples
- [ ] Environment variables documented in .env.template
- [ ] README.md with clear setup instructions
- [ ] CLAUDE.md updated with implementation progress
- [ ] Code comments and docstrings comprehensive

### 16.4 Quality Requirements

- [ ] PEP 8 compliant (can use black for formatting)
- [ ] Type hints on all functions
- [ ] Google-style docstrings on all modules/classes/functions
- [ ] No hardcoded values (all config via environment)
- [ ] Error messages clear and actionable
- [ ] Logging follows best practices (no sensitive data)

---

## 17. Proposed Changes to Structure

### 17.1 Suggested Improvements

Based on the analysis, I propose the following minor adjustments to the structure from INSTRUCTIONS.md:

1. **Add `core/exceptions.py`**: Custom exception hierarchy for better error handling
2. **Add `core/rate_limit.py`**: Separate module for rate limiting setup (follows api/ pattern)
3. **Split schemas**:
   - `schemas/base.py`: Base classes and common schemas
   - `schemas/schema.py`: Strategy-specific schemas
4. **Add `services/` directory**: Separate business logic from routes
5. **Organize tests**: Split into `unit/` and `integration/` subdirectories

### 17.2 Rationale

These changes improve:
- **Maintainability**: Clearer separation of concerns
- **Testability**: Easier to test isolated components
- **Consistency**: Aligns with existing api/ module patterns
- **Scalability**: Easier to add new strategies or features

---

## Appendices

### Appendix A: Example API Usage

#### Threshold Strategy (Sign-based)
```bash
curl -X POST "http://localhost:8001/api/v1/trading/execute" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "threshold",
    "forecast_price": 105.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100000.0,
    "initial_capital": 100000.0,
    "threshold_type": "absolute",
    "threshold_value": 0.0,
    "execution_size": 100.0
  }'
```

#### Return Strategy
```bash
curl -X POST "http://localhost:8001/api/v1/trading/execute" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "return",
    "forecast_price": 108.0,
    "current_price": 100.0,
    "current_position": 100.0,
    "available_cash": 90000.0,
    "initial_capital": 100000.0,
    "position_sizing": "proportional",
    "threshold_value": 0.05,
    "execution_size": 10.0,
    "max_position_size": 150.0,
    "min_position_size": 5.0
  }'
```

#### Quantile Strategy
```bash
curl -X POST "http://localhost:8001/api/v1/trading/execute" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "quantile",
    "forecast_price": 110.0,
    "current_price": 100.0,
    "current_position": 100.0,
    "available_cash": 90000.0,
    "initial_capital": 100000.0,
    "which_history": "close",
    "window_history": 20,
    "quantile_signals": {
      "1": {"range": [0, 5], "signal": "sell", "multiplier": 1.0},
      "2": {"range": [90, 95], "signal": "buy", "multiplier": 0.75}
    },
    "open_history": [95.2, 96.1, ...],
    "high_history": [105.3, 106.2, ...],
    "low_history": [94.1, 95.0, ...],
    "close_history": [100.5, 101.2, ...]
  }'
```

### Appendix B: PARAMETER_STRATEGY_MAP Reference

From sample code analysis, here's the complete parameter mapping:

#### Threshold Strategy
- **Required**: strategy_type, forecast_price, current_price, current_position, available_cash, initial_capital, threshold_type, threshold_value
- **Optional**: execution_size, open_history, high_history, low_history, close_history, which_history, window_history, min_history_length
- **Conditional**: OHLC histories required for 'atr' threshold_type

#### Return Strategy
- **Required**: strategy_type, forecast_price, current_price, current_position, available_cash, initial_capital, position_sizing, threshold_value
- **Optional**: execution_size, max_position_size, min_position_size, open_history, high_history, low_history, close_history, which_history, window_history, min_history_length
- **Conditional**: OHLC histories required for 'normalized' position_sizing

#### Quantile Strategy
- **Required**: strategy_type, forecast_price, current_price, current_position, available_cash, initial_capital, which_history, window_history, quantile_signals, open_history, high_history, low_history, close_history
- **Optional**: position_sizing, execution_size, max_position_size, min_position_size, min_history_length

---

## Next Steps

1. **Await Approval**: Review this implementation plan
2. **Clarifications**: Address any questions or concerns
3. **Begin Implementation**: Start with Phase 1 (Core Infrastructure)
4. **Iterative Development**: Complete each phase, commit progress to CLAUDE.md
5. **Testing**: Comprehensive testing after each phase
6. **Review**: Final review before considering complete

---

**Document Version**: 1.0
**Last Updated**: 2025-11-12
**Status**: Ready for Review
