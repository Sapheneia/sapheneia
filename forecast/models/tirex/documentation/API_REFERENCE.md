# TiRex API Reference

This document provides a detailed reference for all REST API endpoints exposed by the TiRex forecasting model container.

## Overview

The TiRex service exposes endpoints for model initialization, status checking, inference, and graceful shutdown. All core endpoints are mounted under the `/forecast/v1/tirex` prefix.

### Base URL
When running locally via `docker-compose`, the TiRex service is typically exposed on port `12771`.
```
http://localhost:12771/forecast/v1/tirex
```

### Authentication
All model endpoints require API key authentication via a Bearer token in the `Authorization` header:
```
Authorization: Bearer <API_SECRET_KEY>
```

---

## Endpoints

### 1. Initialization
Initializes the TiRex model into memory context.

**Endpoint:** `POST /initialization`
**Auth Required:** Yes

#### Request Body Schema
| Field | Type | Required | Description | Default |
|-------|------|----------|-------------|---------|
| `model_variant` | `string` | No | Hugging Face model variant for TiRex. | `"NX-AI/TiRex"` |
| `device` | `string` | No | Hardware device to load the model onto. Must be `"cpu"`, `"cuda"`, or `"mps"`. | `"cpu"` |

#### Example Request
```json
{
  "model_variant": "NX-AI/TiRex",
  "device": "cpu"
}
```

#### Example Responses
- **200 OK:** `{"message": "Model initialized successfully", "model_status": "ready"}`
- **422 Unprocessable Entity:** `{"detail": [{"loc": ["body", "device"], "msg": "Value error, Device 'invalid' is not supported.", "type": "value_error"}]}`
- **500 Internal Error:** `{"error": "MODEL_ERROR", "message": "Model initialization failed...", "details": {}}`

---

### 2. Status
Checks the current initialization status of the TiRex model.

**Endpoint:** `GET /status`
**Auth Required:** Yes

#### Example Response
```json
{
  "model_status": "ready",
  "details": "Model initialized on cpu"
}
```

---

### 3. Inference
Generates a time-series point forecast using the initialized TiRex model.

**Endpoint:** `POST /inference`
**Auth Required:** Yes

#### Request Body Schema
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `context` | `list[float]` | **Yes** | An array of historical numerical values representing the time-series context. |
| `prediction_length` | `integer` | **Yes** | The number of future time steps to forecast. Must be `> 0`. |

#### Example Request
```json
{
  "context": [1.4, 2.1, 3.8, 4.2],
  "prediction_length": 3
}
```

#### Example Response
```json
{
  "prediction": {
    "point_forecast": [4.9, 5.2, 5.8],
    "metadata": {
      "model_variant": "NX-AI/TiRex",
      "device": "cpu"
    }
  },
  "execution_metadata": {
    "inference_time_ms": 142.5
  }
}
```

---

### 4. Shutdown
Unloads the active TiRex model from memory to free up resources.

**Endpoint:** `POST /shutdown`
**Auth Required:** Yes

#### Example Response
```json
{
  "message": "Model successfully shut down"
}
```
