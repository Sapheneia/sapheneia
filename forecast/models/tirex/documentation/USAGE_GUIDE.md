# TiRex Usage Guide

This guide explains how to integrate and use the TiRex point-forecasting model within the Sapheneia orchestration ecosystem.

## 1. Quick Start (cURL)

The easiest way to verify the TiRex integration is by utilizing direct cURL commands against the `12771` orchestration proxy proxy port. To begin, source your environment variables:

```bash
source .env
export API_KEY=$API_SECRET_KEY
```

### Step A: Check Status
Before issuing inferences, verify whether the container is healthy and whether a model has been loaded into memory.

```bash
curl -X GET "http://localhost:12771/forecast/v1/tirex/status" \
  -H "Authorization: Bearer $API_KEY"
```

### Step B: Initialize the Model
By default, the TiRex container boots uninitialized to conserve memory. Initialize the `NX-AI/TiRex` zero-shot variant directly into CPU (or GPU if supported system-wide):

```bash
curl -X POST "http://localhost:12771/forecast/v1/tirex/initialization" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"model_variant": "NX-AI/TiRex", "device": "cpu"}'
```

### Step C: Run Inference
Pass an array of historical context values corresponding to your time-series data, and define the required `prediction_length` for future horizons:

```bash
curl -X POST "http://localhost:12771/forecast/v1/tirex/inference" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "context": [1.0, 2.5, 3.8, 4.1, 5.9, 6.2, 7.8],
    "prediction_length": 5
  }'
```

---

## 2. Using TiRex via Orchestration SDK

When building trading strategies or analytics dashboards within Sapheneia, you do not need to call the container directly on port `12771`. Instead, use the unified `orchestration` gateway, which automatically routes requests based on the designated `family` parameter.

```python
import httpx
import os

API_KEY = os.getenv("API_SECRET_KEY")
ORCHESTRATOR_URL = "http://localhost:8000/api/v1/forecast/predict"

payload = {
    "request_id": "req-12345",
    "model": {
        "family": "tirex",
        "variant": "NX-AI/TiRex"
    },
    "context": {
        "data": [10.5, 12.1, 11.8, 13.4, 14.2],
        "frequency": "1H"
    },
    "horizon": {
        "length": 3
    }
}

headers = {"Authorization": f"Bearer {API_KEY}"}

response = httpx.post(ORCHESTRATOR_URL, json=payload, headers=headers)
print(response.json())
```

> **Note on Adapters:** The Gateway's `inference_to_tirex()` adapter extracts the `context.data` block and maps `horizon.length` to the `prediction_length` variable automatically, ensuring 1:1 cross-compatibility with models like Chronos and TimesFM!

---

## 3. GPU Acceleration Notes
The TiRex model heavily benefits from CUDA bindings during inference. However, by default, all Sapheneia predictive services are consolidated around a minimalistic `python:3.11-slim` debian orchestration image (`Dockerfile.forecast`). 

Attempting to initialize the container with `{"device": "cuda"}` will dynamically fail upstream with an explicit `422 Validation Error` or `500 Unhandled Exception` depending on your environment. To modify the base image for CUDA optimizations, please refer to the `gpu_support.md` decoupled configuration proposal.
