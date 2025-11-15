# Forecast Application - Quick Reference

Quick reference card for the Forecast Application.

## Common Commands

```bash
# Initialize
./setup.sh init forecast

# Run (venv)
./setup.sh run-venv forecast api      # API only
./setup.sh run-venv forecast ui       # UI only
./setup.sh run-venv forecast all     # Both API and UI

# Run (Docker)
./setup.sh run-docker forecast api    # API only
./setup.sh run-docker forecast ui    # UI only
./setup.sh run-docker forecast all   # Both API and UI

# Stop
./setup.sh stop forecast
```

## Endpoint URLs

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/` | GET | ❌ | 30/min | Root endpoint |
| `/health` | GET | ❌ | 30/min | Health check |
| `/info` | GET | ❌ | 60/min | API information |
| `/models` | GET | ❌ | 60/min | List available models |
| `/forecast/v1/timesfm20/initialization` | POST | ✅ | 5/min | Initialize model |
| `/forecast/v1/timesfm20/status` | GET | ✅ | 60/min | Check model status |
| `/forecast/v1/timesfm20/inference` | POST | ✅ | 10/min | Run inference |
| `/forecast/v1/timesfm20/shutdown` | POST | ✅ | 5/min | Shutdown model |

**Base URL**: `http://localhost:8000`

## Request Templates

### Initialize Model

```json
{
  "backend": "cpu",
  "context_len": 64,
  "horizon_len": 24,
  "checkpoint": "google/timesfm-2.0-500m-pytorch"
}
```

### Run Inference (Basic)

```json
{
  "data_source_url_or_path": "data/uploads/sample_data.csv",
  "data_definition": {
    "price": "target"
  },
  "parameters": {
    "context_len": 64,
    "horizon_len": 24
  }
}
```

### Run Inference (With Covariates)

```json
{
  "data_source_url_or_path": "data/uploads/sample_data.csv",
  "data_definition": {
    "price": "target",
    "volume": "dynamic_numerical",
    "promotion": "dynamic_categorical"
  },
  "parameters": {
    "context_len": 64,
    "horizon_len": 24,
    "use_covariates": true,
    "use_quantiles": true,
    "quantile_indices": [1, 3, 5, 7, 9]
  }
}
```

## Response Format

### Success Response

```json
{
  "field1": "value1",
  "field2": 123,
  "metadata": {
    "timestamp": "2025-11-13T12:00:00"
  }
}
```

### Error Response

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional details"
  }
}
```

## Environment Variables

### Required

```bash
API_SECRET_KEY=your_secret_key_change_me_in_production
```

### Common Optional

```bash
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
ENVIRONMENT=development

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:8080

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_INFERENCE_PER_MINUTE=10

# TimesFM-2.0 Defaults
TIMESFM20_DEFAULT_BACKEND=cpu
TIMESFM20_DEFAULT_CONTEXT_LEN=64
TIMESFM20_DEFAULT_HORIZON_LEN=24
```

## Quick Troubleshooting

### API Won't Start

```bash
# Check port
lsof -i :8000

# Kill process
lsof -ti :8000 | xargs kill -9

# Check logs
tail -f logs/forecast.log
```

### Authentication Error

- Verify `API_SECRET_KEY` in `.env`
- Check header: `Authorization: Bearer YOUR_KEY`
- Try Swagger UI: http://localhost:8000/docs

### File Not Found

**Venv mode:**
```json
{"data_source_url_or_path": "data/uploads/file.csv"}
```

**Docker mode:**
```json
{"data_source_url_or_path": "/app/data/uploads/file.csv"}
```

### Model Not Initialized

```bash
# Check status
curl http://localhost:8000/forecast/v1/timesfm20/status \
  -H "Authorization: Bearer YOUR_KEY"

# Initialize
curl -X POST http://localhost:8000/forecast/v1/timesfm20/initialization \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"backend": "cpu", "context_len": 64, "horizon_len": 24}'
```

## Data Definition Types

| Type | Description | Example |
|------|-------------|---------|
| `target` | Target variable to forecast | `"price": "target"` |
| `dynamic_numerical` | Time-varying numerical feature | `"volume": "dynamic_numerical"` |
| `dynamic_categorical` | Time-varying categorical feature | `"promotion": "dynamic_categorical"` |
| `static_numerical` | Static numerical feature | `"base_price": "static_numerical"` |
| `static_categorical` | Static categorical feature | `"region": "static_categorical"` |

## Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 404 | Not Found |
| 409 | Conflict |
| 429 | Rate Limit Exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

## Access Points

- **API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **API Docs (ReDoc)**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **UI**: http://localhost:8080

## Model Status Values

| Status | Description |
|--------|-------------|
| `uninitialized` | Model not loaded |
| `initializing` | Model is loading |
| `ready` | Model ready for inference |
| `error` | Model encountered an error |

---

**See also:**
- [API Usage Guide](API_USAGE.md) - Detailed API documentation
- [Deployment Guide](DEPLOYMENT.md) - Deployment instructions
- [Examples](EXAMPLES.md) - Code examples
- [Architecture](ARCHITECTURE.md) - System architecture

