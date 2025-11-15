# TimesFM-2.0 - API Reference

Complete API reference for TimesFM-2.0 endpoints.

## Table of Contents

1. [Endpoint Overview](#endpoint-overview)
2. [Initialization Endpoint](#initialization-endpoint)
3. [Status Endpoint](#status-endpoint)
4. [Inference Endpoint](#inference-endpoint)
5. [Shutdown Endpoint](#shutdown-endpoint)
6. [Request Schemas](#request-schemas)
7. [Response Schemas](#response-schemas)
8. [Error Reference](#error-reference)
9. [Rate Limiting](#rate-limiting)

## Endpoint Overview

All TimesFM-2.0 endpoints are under the base path `/forecast/v1/timesfm20/`.

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/initialization` | POST | ✅ | 5/min | Initialize model |
| `/status` | GET | ✅ | 60/min | Check model status |
| `/inference` | POST | ✅ | 10/min | Run forecasting |
| `/shutdown` | POST | ✅ | 5/min | Shutdown model |

**Base URL**: `http://localhost:8000`

## Initialization Endpoint

### POST `/forecast/v1/timesfm20/initialization`

Initialize the TimesFM-2.0 model from specified source.

#### Request

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

**Body:**
```json
{
  "backend": "cpu",
  "context_len": 64,
  "horizon_len": 24,
  "checkpoint": "google/timesfm-2.0-500m-pytorch",
  "local_model_path": null
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `backend` | string | No | `"cpu"` | Computing backend: `cpu`, `gpu`, `tpu`, `mps` |
| `context_len` | integer | No | `64` | Context window length (32-2048) |
| `horizon_len` | integer | No | `24` | Forecast horizon length (1-128) |
| `checkpoint` | string | No | `"google/timesfm-2.0-500m-pytorch"` | HuggingFace checkpoint repo ID |
| `local_model_path` | string | No | `null` | Relative path to local model file |

#### Response

**Success (200):**
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

**Error (409) - Already Initializing:**
```json
{
  "error": "MODEL_INITIALIZATION_IN_PROGRESS",
  "message": "Model initialization already in progress",
  "details": {
    "model_id": "timesfm20",
    "current_status": "initializing"
  }
}
```

**Error (400) - Invalid Parameters:**
```json
{
  "error": "INVALID_PARAMETERS",
  "message": "Invalid parameter values",
  "details": {
    "field": "context_len",
    "issue": "Must be between 32 and 2048"
  }
}
```

#### Example

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/initialization \
  -H "Authorization: Bearer your_secret_key_change_me_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "cpu",
    "context_len": 64,
    "horizon_len": 24
  }'
```

## Status Endpoint

### GET `/forecast/v1/timesfm20/status`

Check the current status of the TimesFM-2.0 model.

#### Request

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
```

#### Response

**Success (200):**
```json
{
  "model_status": "ready",
  "details": "Source: hf:google/timesfm-2.0-500m-pytorch"
}
```

**Status Values:**

| Status | Description |
|--------|-------------|
| `uninitialized` | Model has not been initialized |
| `initializing` | Model is currently being loaded |
| `ready` | Model is ready for inference |
| `error` | Model encountered an error during initialization |

**Error Status Example:**
```json
{
  "model_status": "error",
  "details": "Source: hf:google/timesfm-2.0-500m-pytorch. Error: Out of memory"
}
```

#### Example

```bash
curl http://localhost:8000/forecast/v1/timesfm20/status \
  -H "Authorization: Bearer your_secret_key_change_me_in_production"
```

## Inference Endpoint

### POST `/forecast/v1/timesfm20/inference`

Run forecasting inference on the TimesFM-2.0 model.

#### Request

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

**Body:**
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

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `data_source_url_or_path` | string | ✅ | URL or path to data source |
| `data_definition` | object | ✅ | Column type definitions |
| `parameters` | object | No | Inference parameters |

**Data Definition Types:**

| Type | Description | Example |
|------|-------------|---------|
| `target` | Target variable to forecast | `"price": "target"` |
| `dynamic_numerical` | Time-varying numerical feature | `"volume": "dynamic_numerical"` |
| `dynamic_categorical` | Time-varying categorical feature | `"promotion": "dynamic_categorical"` |
| `static_numerical` | Static numerical feature | `"base_price": "static_numerical"` |
| `static_categorical` | Static categorical feature | `"region": "static_categorical"` |

**Inference Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `context_len` | integer | `64` | Context window length |
| `horizon_len` | integer | `24` | Forecast horizon length |
| `use_covariates` | boolean | `false` | Enable covariates-enhanced forecasting |
| `use_quantiles` | boolean | `false` | Enable quantile forecasting |
| `quantile_indices` | array | `[1, 3, 5, 7, 9]` | Quantile indices to return |

#### Response

**Success (200):**
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
    "target_name": "price"
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

**Error (400) - Model Not Initialized:**
```json
{
  "error": "MODEL_NOT_INITIALIZED",
  "message": "Model must be initialized before running inference",
  "details": {
    "model_id": "timesfm20",
    "current_status": "uninitialized"
  }
}
```

**Error (400) - Data Error:**
```json
{
  "error": "DATA_ERROR",
  "message": "Data error: Local file not found",
  "details": {
    "data_source": "data/uploads/file.csv",
    "issue": "File not found"
  }
}
```

#### Example

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/inference \
  -H "Authorization: Bearer your_secret_key_change_me_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "data_source_url_or_path": "data/uploads/sample_data.csv",
    "data_definition": {
      "price": "target"
    },
    "parameters": {
      "context_len": 64,
      "horizon_len": 24
    }
  }'
```

## Shutdown Endpoint

### POST `/forecast/v1/timesfm20/shutdown`

Unload the TimesFM-2.0 model from memory.

#### Request

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
```

#### Response

**Success (200):**
```json
{
  "message": "Model shutdown successfully",
  "model_status": "uninitialized"
}
```

#### Example

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/shutdown \
  -H "Authorization: Bearer your_secret_key_change_me_in_production"
```

## Request Schemas

### ModelInitInput

```python
{
  "backend": "cpu" | "gpu" | "tpu" | "mps",
  "context_len": int,  # 32-2048
  "horizon_len": int,  # 1-128
  "checkpoint": str,  # Optional, HuggingFace repo ID
  "local_model_path": str  # Optional, relative path
}
```

### InferenceInput

```python
{
  "data_source_url_or_path": str,  # Required, URL or path
  "data_definition": {
    "column_name": "target" | "dynamic_numerical" | "dynamic_categorical" | 
                   "static_numerical" | "static_categorical"
  },
  "parameters": {
    "context_len": int,  # Optional, default: 64
    "horizon_len": int,  # Optional, default: 24
    "use_covariates": bool,  # Optional, default: false
    "use_quantiles": bool,  # Optional, default: false
    "quantile_indices": [int]  # Optional, default: [1, 3, 5, 7, 9]
  }
}
```

## Response Schemas

### ModelInitOutput

```python
{
  "message": str,
  "model_status": "ready" | "error",
  "model_info": {
    "backend": str,
    "context_len": int,
    "horizon_len": int,
    "source": str
  }
}
```

### StatusOutput

```python
{
  "model_status": "uninitialized" | "initializing" | "ready" | "error",
  "details": str  # Optional, additional status information
}
```

### InferenceOutput

```python
{
  "prediction": {
    "point_forecast": [[float]],  # List of forecast series
    "method": str,  # "basic" | "covariates_enhanced"
    "quantile_forecast": [[[float]]],  # Optional, if use_quantiles=true
    "metadata": {
      "input_series_count": int,
      "forecast_length": int,
      "covariates_used": bool,
      "quantiles_available": bool
    },
    "quantile_bands": {  # Optional, if use_quantiles=true
      "quantile_band_0_lower": [float],
      "quantile_band_0_upper": [float],
      "quantile_band_0_label": str,
      ...
    }
  },
  "visualization_data": {
    "historical_data": [float],
    "dates_historical": [str],
    "dates_future": [str],
    "target_name": str
  },
  "execution_metadata": {
    "total_time_seconds": float,
    "execution_time_seconds": float,
    "async_execution": bool,
    "thread_pool": bool,
    "model_version": str,
    "api_version": str
  }
}
```

### ShutdownOutput

```python
{
  "message": str,
  "model_status": "uninitialized"
}
```

## Error Reference

### Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `MODEL_NOT_INITIALIZED` | 400 | Model must be initialized before operation |
| `MODEL_INITIALIZATION_IN_PROGRESS` | 409 | Model is currently initializing |
| `MODEL_INITIALIZATION_ERROR` | 500 | Model initialization failed |
| `DATA_ERROR` | 400 | Data fetching or validation error |
| `DATA_VALIDATION_ERROR` | 400 | Data validation failed |
| `DATA_PROCESSING_ERROR` | 500 | Data processing failed |
| `INVALID_PARAMETERS` | 400 | Invalid parameter values |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |
| `AUTHENTICATION_ERROR` | 401 | Authentication failed |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

### Error Response Format

All errors follow this structure:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional error details"
  }
}
```

## Rate Limiting

### Rate Limits by Endpoint

| Endpoint | Rate Limit | Window |
|----------|------------|--------|
| `/initialization` | 5 requests | 1 minute |
| `/status` | 60 requests | 1 minute |
| `/inference` | 10 requests | 1 minute |
| `/shutdown` | 5 requests | 1 minute |

### Rate Limit Headers

Responses include rate limit information:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1636800000
```

### Rate Limit Exceeded

When rate limit is exceeded:

**Status Code**: `429 Too Many Requests`

**Response:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "detail": "Rate limit exceeded: 10 per 1 minute"
}
```

---

**See also:**
- [Architecture](ARCHITECTURE.md) - Model architecture
- [Data Format](DATA_FORMAT.md) - Data format requirements
- [Parameters](PARAMETERS.md) - Parameter guide
- [Usage Guide](USAGE_GUIDE.md) - Step-by-step usage
- [Examples](EXAMPLES.md) - Code examples

