# Forecast Application - API Usage Guide

Complete guide for using the Forecast Application API.

## Table of Contents

1. [Authentication](#authentication)
2. [Base URL and Endpoints](#base-url-and-endpoints)
3. [Model Discovery](#model-discovery)
4. [Model Operations](#model-operations)
5. [Request/Response Formats](#requestresponse-formats)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Best Practices](#best-practices)

## Authentication

### Overview

All model-specific endpoints require API key authentication via HTTP Bearer token. Discovery and health check endpoints are public.

### Setting Up Authentication

1. Set `API_SECRET_KEY` in your `.env` file:
```bash
API_SECRET_KEY=your_secret_key_change_me_in_production
```

2. Include the API key in request headers:
```bash
Authorization: Bearer your_secret_key_change_me_in_production
```

### Example with curl

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/initialization \
  -H "Authorization: Bearer your_secret_key_change_me_in_production" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Public Endpoints

The following endpoints do not require authentication:
- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /info` - API information
- `GET /models` - List available models

### Security Best Practices

- **Change Default Key**: Never use the default API key in production
- **Use Environment Variables**: Store API keys in `.env` file (never commit to version control)
- **Rotate Keys Regularly**: Change API keys periodically for security
- **Use HTTPS**: Always use HTTPS in production (configure reverse proxy)

## Base URL and Endpoints

### Base URL

- **Development**: `http://localhost:8000`
- **Production**: Configure based on your deployment

### Endpoint Structure

The API follows a hierarchical structure:

```
/forecast/v1/{model_id}/{operation}
```

Where:
- `{model_id}`: Model identifier (e.g., `timesfm20`)
- `{operation}`: Operation type (e.g., `initialization`, `inference`, `status`, `shutdown`)

### Current Models

- **TimesFM-2.0**: `timesfm20`
  - Base path: `/forecast/v1/timesfm20/`
  - See [TimesFM-2.0 API Reference](../models/timesfm20/documentation/API_REFERENCE.md) for detailed endpoint documentation

## Model Discovery

### List Available Models

Get a list of all registered models:

```bash
curl http://localhost:8000/models
```

**Response:**
```json
{
  "models": {
    "timesfm20": {
      "name": "TimesFM 2.0",
      "version": "2.0.500m",
      "description": "Google's TimesFM 2.0 - 500M parameter foundation model",
      "module": "forecast.models.timesfm20",
      "router_path": "forecast.models.timesfm20.routes.endpoints",
      "service_path": "forecast.models.timesfm20.services.model",
      "default_port": 8001,
      "status": "active"
    }
  },
  "count": 1
}
```

### API Information

Get comprehensive API information:

```bash
curl http://localhost:8000/info
```

**Response:**
```json
{
  "name": "Sapheneia Inference API",
  "description": "REST API for time series forecasting models...",
  "version": "2.0.0",
  "api_host": "0.0.0.0",
  "api_port": 8000,
  "available_models": ["timesfm20"],
  "documentation": {
    "swagger": "/docs",
    "redoc": "/redoc",
    "openapi_json": "/openapi.json"
  },
  "features": {
    "mlflow_tracking": false,
    "api_authentication": true
  }
}
```

### Health Check

Check API and model health:

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-13T12:00:00",
  "api_version": "2.0.0",
  "models": {
    "timesfm20": {
      "status": "ready",
      "error": null
    }
  }
}
```

## Model Operations

### Workflow Overview

The typical workflow for using a forecasting model:

1. **Initialize Model**: Load model into memory
2. **Check Status**: Verify model is ready
3. **Run Inference**: Execute forecasting
4. **Shutdown Model** (optional): Unload model from memory

### TimesFM-2.0 Operations

For detailed TimesFM-2.0 endpoint documentation, see [TimesFM-2.0 API Reference](../models/timesfm20/documentation/API_REFERENCE.md).

#### 1. Initialize Model

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/initialization \
  -H "Authorization: Bearer your_secret_key_change_me_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "cpu",
    "context_len": 64,
    "horizon_len": 24,
    "checkpoint": "google/timesfm-2.0-500m-pytorch"
  }'
```

#### 2. Check Model Status

```bash
curl http://localhost:8000/forecast/v1/timesfm20/status \
  -H "Authorization: Bearer your_secret_key_change_me_in_production"
```

#### 3. Run Inference

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/inference \
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

#### 4. Shutdown Model

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/shutdown \
  -H "Authorization: Bearer your_secret_key_change_me_in_production"
```

## Request/Response Formats

### Request Format

All POST requests use JSON format:

```json
{
  "field1": "value1",
  "field2": 123,
  "field3": {
    "nested": "value"
  }
}
```

### Response Format

Successful responses return JSON:

```json
{
  "field1": "value1",
  "field2": 123,
  "metadata": {
    "timestamp": "2025-11-13T12:00:00"
  }
}
```

### Error Response Format

Error responses follow a structured format:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional error details"
  }
}
```

### Common HTTP Status Codes

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication failed
- `404 Not Found`: Endpoint or resource not found
- `409 Conflict`: Resource conflict (e.g., model already initializing)
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

## Error Handling

### Error Types

The API uses a structured error hierarchy:

- **ModelError**: Model-related errors
  - `ModelNotInitializedError`: Model not initialized
  - `ModelInitializationError`: Model initialization failed
  - `ModelInferenceError`: Inference execution failed

- **DataError**: Data-related errors
  - `DataFetchError`: Data fetching failed
  - `DataValidationError`: Data validation failed
  - `DataProcessingError`: Data processing failed

- **ConfigurationError**: Configuration errors

### Error Response Example

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

### Error Handling Best Practices

1. **Check Status Codes**: Always check HTTP status codes
2. **Parse Error Responses**: Extract error details from response body
3. **Handle Rate Limits**: Implement exponential backoff for 429 errors
4. **Retry Logic**: Implement retry logic for transient errors (500, 503)
5. **Log Errors**: Log error details for debugging

## Rate Limiting

### Overview

The API implements rate limiting to prevent abuse and ensure fair usage.

### Rate Limit Configuration

- **Default**: 60 requests per minute
- **Inference Endpoints**: 10 requests per minute (stricter)
- **Health/Discovery**: 30 requests per minute

### Rate Limit Headers

Responses include rate limit information:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1636800000
```

### Rate Limit Exceeded

When rate limit is exceeded, the API returns:

- **Status Code**: `429 Too Many Requests`
- **Response Body**:
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Please try again later.",
  "details": {
    "limit": 60,
    "window": "1 minute",
    "retry_after": 30
  }
}
```

### Rate Limiting Best Practices

1. **Respect Rate Limits**: Implement exponential backoff
2. **Monitor Headers**: Check `X-RateLimit-Remaining` to avoid hitting limits
3. **Cache Responses**: Cache model status and metadata to reduce requests
4. **Batch Operations**: Combine multiple operations when possible

## Best Practices

### General Best Practices

1. **Use HTTPS in Production**: Always use HTTPS for API calls in production
2. **Store API Keys Securely**: Never hardcode API keys in source code
3. **Handle Errors Gracefully**: Implement proper error handling and retry logic
4. **Monitor Rate Limits**: Track rate limit headers to avoid exceeding limits
5. **Use Connection Pooling**: Reuse HTTP connections for better performance
6. **Validate Data**: Validate data before sending requests
7. **Log Requests**: Log API requests for debugging and auditing

### Model Initialization Best Practices

1. **Initialize Once**: Initialize model once and reuse for multiple inferences
2. **Check Status**: Always check model status before running inference
3. **Handle Initialization Errors**: Implement retry logic for initialization failures
4. **Monitor Memory**: Monitor memory usage when loading large models

### Inference Best Practices

1. **Validate Data Format**: Ensure data matches expected format before sending
2. **Use Appropriate Parameters**: Choose context_len and horizon_len based on your data
3. **Handle Large Datasets**: For large datasets, consider batch processing
4. **Cache Results**: Cache forecast results when appropriate
5. **Monitor Performance**: Track inference times and optimize as needed

### Data Source Best Practices

1. **Use Relative Paths in Venv**: Use relative paths like `data/uploads/file.csv` in venv mode
2. **Use Absolute Paths in Docker**: Use absolute paths like `/app/data/uploads/file.csv` in Docker mode
3. **Validate File Existence**: Check file existence before sending requests
4. **Handle HTTP URLs**: Ensure HTTP URLs are accessible and return valid CSV data
5. **Secure Local Files**: Ensure local files are within allowed directories

### Performance Best Practices

1. **Reuse Model Instances**: Don't reinitialize model for each inference
2. **Use Async Requests**: Use async HTTP clients for better performance
3. **Batch Operations**: Batch multiple operations when possible
4. **Monitor Response Times**: Track API response times and optimize slow operations
5. **Use Compression**: Enable GZip compression for large responses

### Security Best Practices

1. **Change Default API Key**: Always change default API key in production
2. **Use Strong Keys**: Use strong, randomly generated API keys
3. **Rotate Keys**: Rotate API keys periodically
4. **Restrict CORS**: Configure CORS to allow only trusted origins
5. **Validate Inputs**: Validate all inputs to prevent injection attacks
6. **Monitor Access**: Monitor API access for suspicious activity

---

**See also:**
- [Architecture Documentation](ARCHITECTURE.md) - System architecture
- [Deployment Guide](DEPLOYMENT.md) - Deployment instructions
- [Examples](EXAMPLES.md) - Code examples
- [Quick Reference](QUICK_REFERENCE.md) - Quick reference card
- [TimesFM-2.0 API Reference](../models/timesfm20/documentation/API_REFERENCE.md) - Model-specific API documentation

