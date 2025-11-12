# Sapheneia v1.0

A scalable, multi-model time series forecasting platform built on FastAPI. Currently supports Google's TimesFM-2.0 with architecture ready for multiple models (Chronos, Prophet, etc.). Designed for production deployments with REST API, Docker support, and MLOps integration.

## 🎯 What's New in v2.0

- **Multi-Model Architecture**: Extensible framework supporting multiple forecasting models
- **Model Registry**: Centralized catalog of available models with metadata
- **REST API**: FastAPI backend with auto-generated OpenAPI documentation
- **Flexible Deployment**: Run all models via single API or as separate services
- **API Authentication**: Secure API key-based authentication
- **Docker Support**: Parameterized Dockerfiles for easy multi-model deployment
- **Unified Management**: Single `setup.sh` script for all operations
- **Production Ready**: Health checks, logging, error handling, and CORS
- **Optimized Defaults**: context_len set to **64** for best performance
- **Trading Strategies API**: New trading strategies application for investment strategy execution (v2.1)

## 🚀 Quick Start

### Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/labrem/sapheneia.git
cd sapheneia

# 2. Initialize environment (installs dependencies, creates .env)
# For forecast application (default)
./setup.sh init forecast

# For trading application
./setup.sh init trading

# 3. Edit .env file and set your API keys
nano .env  # IMPORTANT: Change default API keys!
# - API_SECRET_KEY (for forecast API)
# - TRADING_API_KEY (for trading API, min 32 chars in production)
```

### Running the Applications

Sapheneia includes two independent applications:
- **Forecast Application**: Time series forecasting API and UI (ports 8000, 8080)
- **Trading Application**: Trading strategies API (port 9000)

**Option 1: Virtual Environment (Recommended for Development)**

**Forecast Application:**
```bash
# Run both API and UI
./setup.sh run-venv forecast all

# Or run individually
./setup.sh run-venv forecast api      # API only on port 8000
./setup.sh run-venv forecast ui       # UI only on port 8080
```

**Trading Application:**
```bash
# Run trading API
./setup.sh run-venv trading           # Trading API on port 9000
```

**Stop Services:**
```bash
./setup.sh stop forecast              # Stop forecast services
./setup.sh stop trading               # Stop trading services
```

**Option 2: Docker (Recommended for Production)**

**Forecast Application:**
```bash
# Run both API and UI
./setup.sh run-docker forecast all

# Or run individually
./setup.sh run-docker forecast api
./setup.sh run-docker forecast ui
```

**Trading Application:**
```bash
# Run trading API
./setup.sh run-docker trading
```

**Stop Services:**
```bash
./setup.sh stop forecast              # Stop forecast services
./setup.sh stop trading               # Stop trading services
```

### Available Commands

**Forecast Application:**
```bash
./setup.sh init forecast                    # Initialize forecast application
./setup.sh run-venv forecast api           # Run API with virtual environment
./setup.sh run-venv forecast ui            # Run UI with virtual environment
./setup.sh run-venv forecast all           # Run both API and UI
./setup.sh run-docker forecast api         # Run API with Docker
./setup.sh run-docker forecast ui          # Run UI with Docker
./setup.sh run-docker forecast all         # Run both with Docker Compose
./setup.sh stop forecast                   # Stop forecast services
./setup.sh --help forecast                 # Help for forecast application
```

**Trading Application:**
```bash
./setup.sh init trading                    # Initialize trading application
./setup.sh run-venv trading               # Run trading API with virtual environment
./setup.sh run-docker trading             # Run trading API with Docker
./setup.sh stop trading                    # Stop trading services
./setup.sh --help trading                  # Help for trading application
```

**General:**
```bash
./setup.sh --help                          # General help (both applications)
```

## 📖 Access Points

**Forecast Application:**
- **API Documentation (Swagger)**: http://localhost:8000/docs
- **API Documentation (ReDoc)**: http://localhost:8000/redoc
- **API Health Check**: http://localhost:8000/health
- **Model Registry**: http://localhost:8000/models
- **Web UI**: http://localhost:8080

**Trading Application:**
- **API Documentation (Swagger)**: http://localhost:9000/docs
- **API Documentation (ReDoc)**: http://localhost:9000/redoc
- **API Health Check**: http://localhost:9000/health
- **Trading Strategies**: http://localhost:9000/trading/strategies
- **Trading Status**: http://localhost:9000/trading/status

## 🏗️ Architecture

### Project Structure

```
sapheneia/
├── api/                                    # FastAPI Backend
│   ├── main.py                             # Application entry point
│   ├── core/                               # Shared infrastructure
│   │   ├── config.py                       # Settings & environment vars
│   │   ├── security.py                     # API key authentication
│   │   └── data.py                         # Data fetching utilities
│   └── models/                             # Model modules (NEW)
│       ├── __init__.py                     # Model registry
│       └── timesfm20/                      # TimesFM-2.0 implementation
│           ├── routes/endpoints.py         # REST API endpoints
│           ├── schemas/schema.py           # Pydantic models
│           ├── services/
│           │   ├── model.py                # Model management
│           │   └── data.py                 # Data transformation
│           └── local/                      # Model artifacts cache
│
├── ui/                                     # Flask Frontend
│   ├── app.py                              # Web application
│   ├── api_client.py                       # REST API client
│   ├── templates/                          # HTML templates
│   └── static/                             # CSS/JS assets
│
├── trading/                                # Trading Strategies API (NEW)
│   ├── main.py                             # FastAPI application entry point
│   ├── core/                               # Core infrastructure
│   │   ├── config.py                       # Settings & environment vars
│   │   ├── security.py                     # API key authentication
│   │   ├── exceptions.py                   # Custom exception hierarchy
│   │   └── rate_limit.py                   # Rate limiting configuration
│   ├── routes/                             # API endpoints
│   │   └── endpoints.py                    # Trading strategy endpoints
│   ├── schemas/                            # Pydantic schemas
│   │   └── schema.py                       # Request/response models
│   ├── services/                           # Business logic
│   │   └── trading.py                      # TradingStrategy class
│   ├── tests/                              # Test suite
│   │   ├── unit/                           # Unit tests
│   │   └── integration/                    # Integration tests
│   └── sample/                             # Sample code reference
│
├── data/                                   # Shared data directory
│   ├── uploads/                            # User uploaded files
│   └── results/                            # Forecast outputs
│
├── notebooks/                              # Jupyter notebooks
├── logs/                                   # Application logs
│
├── Dockerfile.api                          # API Docker (multi-model)
├── Dockerfile.ui                           # UI Docker
├── Dockerfile.trading                      # Trading API Docker (NEW)
├── docker-compose.yml                      # Service orchestration
├── setup.sh                                # Unified management script
├── .env                                    # Local configuration
├── .env.template                           # Configuration template
└── pyproject.toml                          # Python dependencies
```

### Multi-Model Design

The architecture supports running multiple forecasting models simultaneously:

**Current Models:**
- TimesFM 2.0 (500M parameters) - Active

**Planned Models:**
- Chronos (Amazon)
- Prophet (Meta)
- Custom models

**Deployment Options:**

1. **Single API Gateway** (Default)
   - All models accessible via http://localhost:8000
   - Endpoints: `/api/v1/timesfm20/*`, `/api/v1/chronos/*`, etc.
   - Easiest for orchestrators and load balancers

2. **Separate Model Services** (Optional)
   - Each model runs in its own container on dedicated port
   - TimesFM: http://localhost:8001
   - Chronos: http://localhost:8002
   - Prophet: http://localhost:8003
   - Enable by uncommenting services in `docker-compose.yml`

## 🔌 API Endpoints

### Discovery & Health

- `GET /` - Root endpoint with API info
- `GET /health` - Health check with model status
- `GET /info` - Detailed API information
- `GET /models` - List all available models

### TimesFM-2.0 Model

**Base Path**: `/api/v1/timesfm20/`

All endpoints require API authentication:
```bash
Authorization: Bearer YOUR_API_SECRET_KEY
```

#### 1. Initialize Model

Load TimesFM model into memory:

```bash
curl -X POST http://localhost:8000/api/v1/timesfm20/initialization \
  -H "Authorization: Bearer your_secret_key_change_me_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "cpu",
    "context_len": 64,
    "horizon_len": 24,
    "checkpoint": "google/timesfm-2.0-500m-pytorch"
  }'
```

**Response:**
```json
{
  "message": "Model initialized successfully from hf:google/timesfm-2.0-500m-pytorch",
  "model_status": "ready",
  "model_info": {
    "backend": "cpu",
    "context_len": 64,
    "horizon_len": 24,
    "source": "hf:google/timesfm-2.0-500m-pytorch"
  }
}
```

#### 2. Check Model Status

```bash
curl http://localhost:8000/api/v1/timesfm20/status \
  -H "Authorization: Bearer your_secret_key_change_me_in_production"
```

**Response:**
```json
{
  "model_status": "ready",
  "details": "Source: hf:google/timesfm-2.0-500m-pytorch"
}
```

#### 3. Run Inference

**Important Path Handling:**
- **Venv mode**: Use relative paths like `data/uploads/file.csv`
- **Docker mode**: Use absolute paths like `/app/data/uploads/file.csv`

```bash
curl -X POST http://localhost:8000/api/v1/timesfm20/inference \
  -H "Authorization: Bearer your_secret_key_change_me_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "data_source_url_or_path": "data/uploads/sample_data.csv",
    "data_definition": {
      "price": "target",
      "volume": "dynamic_numerical"
    },
    "parameters": {
      "context_len": 64,
      "horizon_len": 24,
      "use_covariates": true,
      "use_quantiles": true,
      "quantile_indices": [1, 3, 5, 7, 9]
    }
  }'
```

**Response:**
```json
{
  "prediction": {
    "point_forecast": [[39808.79, 40049.30, 40379.86, ...]],
    "method": "covariates_enhanced",
    "quantile_forecast": [[[...], [...], [...]]],
    "metadata": {
      "input_series_count": 1,
      "forecast_length": 24,
      "covariates_used": true,
      "quantiles_available": true
    },
    "quantile_bands": {
      "quantile_band_0_lower": [...],
      "quantile_band_0_upper": [...],
      "quantile_band_0_label": "Q10–Q30",
      ...
    }
  },
  "visualization_data": {
    "historical_data": [33113.91, 34169.22, 37253.25, ...],
    "dates_historical": ["2022-08-10T00:00:00", "2022-08-17T00:00:00", ...],
    "dates_future": ["2023-11-01T00:00:00", "2023-11-08T00:00:00", ...],
    "target_name": "btc_price"
  },
  "execution_metadata": {
    "total_time_seconds": 0.329,
    "execution_time_seconds": 0.329,
    "async_execution": true,
    "thread_pool": true,
    "model_version": "2.0.0",
    "api_version": "2.0.0"
  }
}
```

#### 4. Shutdown Model

Unload model from memory:

```bash
curl -X POST http://localhost:8000/api/v1/timesfm20/shutdown \
  -H "Authorization: Bearer your_secret_key_change_me_in_production"
```

## 📈 Trading Strategies Application

The Trading Strategies API provides a stateless service for executing investment trading strategies. It supports three strategy types: threshold-based, return-based, and quantile-based strategies.

### Quick Start

```bash
# 1. Initialize trading application
./setup.sh init trading

# 2. Set TRADING_API_KEY in .env (min 32 characters)
nano .env

# 3. Run trading API
./setup.sh run-venv trading

# Or with Docker
./setup.sh run-docker trading
```

### API Usage Examples

#### 1. List Available Strategies

```bash
curl http://localhost:9000/trading/strategies
```

#### 2. Execute Threshold Strategy

```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
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

**Response:**
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

#### 3. Execute Return Strategy

```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "return",
    "forecast_price": 108.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100000.0,
    "initial_capital": 100000.0,
    "position_sizing": "fixed",
    "threshold_value": 0.05,
    "execution_size": 10.0
  }'
```

#### 4. Execute Quantile Strategy

```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "quantile",
    "forecast_price": 92.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100000.0,
    "initial_capital": 100000.0,
    "which_history": "close",
    "window_history": 20,
    "quantile_signals": {
      "1": {"range": [0, 20], "signal": "buy", "multiplier": 1.0},
      "2": {"range": [80, 100], "signal": "sell", "multiplier": 1.0}
    },
    "position_sizing": "fixed",
    "execution_size": 10.0,
    "open_history": [100.0, 101.0, 99.0, ...],
    "high_history": [105.0, 106.0, 104.0, ...],
    "low_history": [95.0, 96.0, 94.0, ...],
    "close_history": [100.0, 101.0, 99.0, ...]
  }'
```

### Strategy Types

- **Threshold Strategy**: Price difference-based with configurable thresholds (absolute, percentage, std_dev, ATR)
- **Return Strategy**: Expected return-based with position sizing (fixed, proportional, normalized)
- **Quantile Strategy**: Empirical quantile-based using historical price distribution

### Documentation

For detailed documentation, see:
- **API Usage Guide**: [trading/API_USAGE.md](trading/API_USAGE.md)
- **Strategy Guide**: [trading/STRATEGIES.md](trading/STRATEGIES.md)
- **Deployment Guide**: [trading/DEPLOYMENT.md](trading/DEPLOYMENT.md)
- **Quick Reference**: [trading/QUICK_REFERENCE.md](trading/QUICK_REFERENCE.md)
- **Examples**: [trading/EXAMPLES.md](trading/EXAMPLES.md)

## ⚙️ Configuration

### Environment Variables (`.env`)

**Forecast Application - Required:**
```bash
API_SECRET_KEY=your_secret_key_change_me_in_production  # CHANGE THIS!
```

**Trading Application - Required:**
```bash
TRADING_API_KEY=your_trading_api_key_min_32_chars_in_production  # CHANGE THIS! (min 32 chars)
```

**API Settings:**
```bash
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

**Model Ports (for separate services):**
```bash
TIMESFM20_MODEL_PORT=8001
IMESFM25_MODEL_PORT=8002
FLOWSTATE91M_MODEL_PORT=8003
```

**TimesFM-2.0 Defaults:**
```bash
TIMESFM20_DEFAULT_BACKEND=cpu
TIMESFM20_DEFAULT_CONTEXT_LEN=64
TIMESFM20_DEFAULT_HORIZON_LEN=24
TIMESFM20_DEFAULT_CHECKPOINT=google/timesfm-2.0-500m-pytorch
```

**Trading Application Settings:**
```bash
TRADING_API_HOST=0.0.0.0
TRADING_API_PORT=9000
ENVIRONMENT=development  # development, staging, or production
LOG_LEVEL=INFO

# CORS Settings
CORS_ALLOWED_ORIGINS=http://localhost:8080,http://localhost:3000
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_EXECUTE_PER_MINUTE=10  # Stricter limit for execute endpoint
```

**UI Settings:**
```bash
UI_API_BASE_URL=http://localhost:8000
UI_PORT=8080
```

**MLOps (Optional):**
```bash
MLFLOW_TRACKING_URI=http://localhost:5000
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Data Definition Format

When calling the inference endpoint, specify column types:

```json
{
  "target_price": "target",
  "sales_volume": "dynamic_numerical",
  "promotion_active": "dynamic_categorical",
  "region": "static_categorical",
  "base_price": "static_numerical"
}
```

**Valid Types:**
- `target` - Target variable to forecast (required, one per request)
- `dynamic_numerical` - Time-varying numerical features
- `dynamic_categorical` - Time-varying categorical features
- `static_numerical` - Static numerical features
- `static_categorical` - Static categorical features

## 🐳 Docker Usage

### Start Services

```bash
# Using setup.sh (recommended)
./setup.sh run-docker all

# Or using docker-compose directly
docker-compose up -d
```

### View Logs

```bash
# All services
docker-compose logs -f

# API only
docker-compose logs -f api

# UI only
docker-compose logs -f ui
```

### Stop Services

```bash
# Using setup.sh (recommended)
./setup.sh stop

# Or using docker commands
docker stop sapheneia-api sapheneia-ui
docker rm sapheneia-api sapheneia-ui
```

### Rebuild Images

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Multi-Model Deployment

To run models as separate services, edit `docker-compose.yml`:

```yaml
# Uncomment this section
api-timesfm20:
  build:
    context: .
    dockerfile: Dockerfile.api
    args:
      MODEL_NAME: timesfm20
      MODEL_PORT: 8001
  container_name: sapheneia-api-timesfm20
  ports:
    - "8001:8001"
  # ... rest of config
```

---

## ⚠️ Deployment Limitations

### Current State Management

**IMPORTANT**: The API currently uses **module-level state** for model instances, which has the following limitations:

#### Limitations

- **Single Worker Only**: Each model service must run with `UVICORN_WORKERS=1`
- **No Horizontal Scaling**: Cannot run multiple instances of the same model with shared state
- **State Non-Persistent**: Model state is lost on process restart
- **Memory Isolation**: Each container has its own isolated state

#### What Works

✅ **Multiple Different Models**: You can run TimesFM, Chronos, and Prophet simultaneously in separate containers
✅ **Concurrent Requests**: Single worker handles concurrent requests safely (with thread locks from Phase 4.2)
✅ **Model Isolation**: Each model's state is completely isolated from others

#### What Doesn't Work

❌ **Multiple Workers per Model**: Running `--workers 4` will cause state conflicts
❌ **Horizontal Scaling**: Cannot load-balance across multiple containers of the same model
❌ **Parallel Benchmarking**: Cannot run parallel tasks on the same model instance

#### Future Solution: Redis State Backend

For production deployments requiring:
- High throughput (multiple workers per model)
- Horizontal scaling (multiple containers per model)
- Parallel benchmarking and testing
- State persistence across restarts

**→ Implement Redis state backend (see `REMEDIATION_PLAN.md` Phase 4, Task 4.3)**

This will enable:
- Distributed state management across processes
- Multiple workers: `UVICORN_WORKERS=4+`
- Horizontal scaling with load balancing
- Persistent state storage
- Distributed locking for thread safety

See [Phase 4 documentation](REMEDIATION_PLAN.md#phase-4-state-management-week-2-days-1-3) for implementation details.

---

## 📊 Features

### Core Capabilities

- ✅ **TimesFM-2.0 Integration**: Google's 500M parameter foundation model
- ✅ **Quantile Forecasting**: Uncertainty quantification (10-90th percentiles)
- ✅ **Covariates Support**: Dynamic/static, numerical/categorical variables
- ✅ **Multiple Data Sources**: Local files, HTTP URLs, planned: S3/GCS
- ✅ **Interactive Visualization**: Plotly-based charts in UI
- ✅ **API Documentation**: Auto-generated OpenAPI/Swagger docs
- ✅ **Model Registry**: Centralized model discovery and metadata

### Model Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `backend` | cpu | cpu/gpu/tpu | Computing backend |
| `context_len` | 64 | 32-2048 | Historical window length |
| `horizon_len` | 24 | 1-128 | Forecast horizon |
| `checkpoint` | google/timesfm-2.0-500m-pytorch | - | HuggingFace model ID |

### Quantile Indices

The model outputs 10 quantile forecasts:
- Index 0: Legacy mean (skip this)
- Index 1: Q10 (10th percentile)
- Index 2: Q20
- Index 3: Q30
- Index 4: Q40
- Index 5: Q50 (median)
- Index 6: Q60
- Index 7: Q70
- Index 8: Q80
- Index 9: Q90 (90th percentile)

## 🔒 Security

### API Authentication

All model endpoints require authentication:

```bash
Authorization: Bearer YOUR_API_KEY
```

Set `API_SECRET_KEY` in `.env` file.

### Best Practices

1. **Change the default API key** immediately after setup
2. **Use environment variables** for all secrets
3. **Use HTTPS** in production (configure reverse proxy)
4. **Restrict CORS** to specific origins (edit `api/main.py`)
5. **Implement rate limiting** for production
6. **Keep dependencies updated** regularly
7. **Never commit `.env`** to version control

## 🧪 Testing the API

### Using Interactive Docs

1. Start API: `./setup.sh run-venv api`
2. Open http://localhost:8000/docs
3. Click "Authorize" button
4. Enter your API key from `.env`
5. Try endpoints directly in browser

### Using curl

See examples in the [API Endpoints](#-api-endpoints) section.

### Using Python

```python
import requests

API_URL = "http://localhost:8000"
API_KEY = "your_secret_key_change_me_in_production"

headers = {"Authorization": f"Bearer {API_KEY}"}

# List available models
response = requests.get(f"{API_URL}/models")
print(response.json())

# Initialize TimesFM
response = requests.post(
    f"{API_URL}/api/v1/timesfm20/initialization",
    headers=headers,
    json={
        "backend": "cpu",
        "context_len": 64,
        "horizon_len": 24
    }
)
print(response.json())

# Run inference
response = requests.post(
    f"{API_URL}/api/v1/timesfm20/inference",
    headers=headers,
    json={
        "data_source_url_or_path": "data/uploads/sample.csv",
        "data_definition": {"price": "target"},
        "parameters": {
            "context_len": 64,
            "horizon_len": 24
        }
    }
)
print(response.json())
```

## 📚 Research & Development

### Jupyter Notebooks

Note: The `src/` directory has been migrated to `api/` and `ui/` modules. For existing notebooks, please update imports to use the new module structure.

```bash
# Activate environment
source .venv/bin/activate

# Start Jupyter
uv run jupyter notebook

# Open notebooks in notebooks/
```

### Existing Code Compatibility

Update your notebooks to use the new module structure:

```python
from api.core.model_wrapper import TimesFMModel
from api.core.data_processing import DataProcessor
from api.core.forecasting import Forecaster
from ui.visualization import Visualizer

# Updated code with proper module imports
```

## 🚀 Adding New Models

### Step-by-Step Guide

**Example: Adding Chronos**

1. **Create model directory:**
```bash
mkdir -p api/models/chronos/{routes,schemas,services,local}
```

2. **Implement model code:**
- Copy structure from `api/models/timesfm20/`
- Implement Chronos-specific logic
- Update imports and schemas

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

5. **Update Dockerfile (optional):**
```dockerfile
# In Dockerfile.api
RUN if [ "$MODEL_NAME" = "chronos" ] || [ "$MODEL_NAME" = "all" ]; then \
        uv pip install --system chronos-forecasting; \
    fi
```

6. **Test:**
```bash
curl http://localhost:8000/models
# Should show both timesfm20 and chronos
```

## 🔧 Troubleshooting

### API Won't Start

```bash
# Check if port is in use
lsof -i :8000

# Kill process if needed
lsof -ti :8000 | xargs kill -9

# Check logs
tail -f logs/api.log

# Verify environment
cat .env
```

### Authentication Errors

**Symptoms:**
```json
{"detail":"Not authenticated"}
```

**Solutions:**
- Verify API key matches in `.env`
- Check header format: `Authorization: Bearer YOUR_KEY`
- Ensure no extra spaces in header
- Try in Swagger UI first: http://localhost:8000/docs

### File Not Found Errors

**Symptoms:**
```json
{"detail":"Data error: Local file not found: /app/data/uploads/file.csv"}
```

**Solutions:**

**Venv mode** - Use relative paths:
```json
{
  "data_source_url_or_path": "data/uploads/file.csv"
}
```

**Docker mode** - Use absolute paths:
```json
{
  "data_source_url_or_path": "/app/data/uploads/file.csv"
}
```

### Model Loading Issues

**Symptoms:**
- Out of memory errors
- Slow initialization
- Download failures

**Solutions:**
- Ensure sufficient RAM (4GB+ for TimesFM)
- Verify internet connection (HuggingFace downloads)
- Check disk space (3.8GB for TimesFM weights)
- Review logs: `docker-compose logs api`

### Docker Issues

```bash
# Rebuild from scratch
./setup.sh stop
docker-compose down -v
docker-compose build --no-cache
./setup.sh run-docker all

# Check container status
docker ps -a

# View logs
docker-compose logs -f api

# Check resources
docker stats
```

### Docker Won't Stop

If `./setup.sh stop` doesn't work:

```bash
# Manual stop
docker stop sapheneia-api sapheneia-ui
docker rm sapheneia-api sapheneia-ui

# Or use Docker Desktop GUI
```

## 📝 Migration from v1.0

If upgrading from the original Flask version:

1. **Notebooks**: No changes - continue using `src/` modules
2. **UI**: Now communicates via REST API instead of direct imports
3. **Deployment**: Use `./setup.sh` instead of manual commands
4. **Configuration**: Move settings to `.env` file
5. **Authentication**: Add API key to all programmatic requests

## 🔮 Future Enhancements

### Planned Features

- [ ] Additional models (Chronos, Prophet, custom models)
- [ ] MLflow integration for experiment tracking
- [ ] Celery for async inference jobs
- [ ] Redis for distributed state management
- [ ] Batch inference endpoints
- [ ] WebSocket support for real-time updates
- [ ] Advanced authentication (OAuth2, JWT)
- [ ] Rate limiting and quotas
- [ ] Prometheus metrics
- [ ] Grafana dashboards
- [ ] S3/GCS data source support
- [ ] Model versioning and A/B testing

### Contributing

To add a new model or feature, see [CLAUDE.md](CLAUDE.md) for development guidelines.

## 📞 Support & Documentation

- **API Docs**: http://localhost:8000/docs
- **Development Log**: [CLAUDE.md](CLAUDE.md)
- **Quick Start**: [local/API_QUICK_START.md](local/API_QUICK_START.md)
- **Implementation Details**: [local/IMPLEMENTATION_SUMMARY.md](local/IMPLEMENTATION_SUMMARY.md)

## 📜 License

This project builds upon Google's TimesFM foundation model. Please refer to the original TimesFM license and terms of use.

## 🙏 Acknowledgments

- **Google Research** for TimesFM foundation model
- **FastAPI** framework and community
- **Anthropic's Claude** for development assistance

---

**Sapheneia v2.0** - Production-Ready Multi-Model Time Series Forecasting Platform
