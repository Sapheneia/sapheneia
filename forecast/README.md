# Forecast Service

Stateless time-series inference. One container per model variant; a thin
gateway routes requests by family. Loads HuggingFace weights into a
**module-level singleton** at first `initialize` call, then serves inference
synchronously from that singleton (concurrent requests serialize behind a
threading lock).

## Endpoints

All non-`/health` endpoints require `Authorization: Bearer ${API_SECRET_KEY}`.

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/health` | FastAPI liveness; does not check model state |
| GET    | `/`       | Service banner |
| GET    | `/info`   | Capabilities + auth flag |
| GET    | `/models` | Available models (from `shared/model_registry.py`) |
| POST   | `/forecast/v1/timesfm20/initialization` | Load TimesFM 2.0 from `TIMESFM20_DEFAULT_CHECKPOINT` |
| GET    | `/forecast/v1/timesfm20/status`         | `ready` \| `initializing` \| `error` |
| POST   | `/forecast/v1/timesfm20/inference`      | Run inference with `context`, `prediction_length`, `num_samples` |
| POST   | `/forecast/v1/timesfm20/shutdown`       | Free model from memory |
| POST   | `/forecast/v1/chronos/initialization`   | Load Chronos variant from `MODEL_VARIANT` |
| GET    | `/forecast/v1/chronos/status`           | Same shape |
| POST   | `/forecast/v1/chronos/inference`        | Same shape |
| POST   | `/forecast/v1/chronos/shutdown`         | Same shape |
| POST   | `/forecast/v1/inference`                | Generic inference (forwards to the family of the loaded model) |

### Inference request/response shapes

Both `/timesfm20/inference` and `/chronos/inference` accept:
```json
{
  "context": [number, ...],     // historical values, length <= context window
  "prediction_length": int,     // forecast horizon (model output window)
  "num_samples": int            // optional; ignored by deterministic models
}
```

Response (current code; both families):
```json
{
  "forecast": {"values": [number, ...]},
  "quantiles": [
    {"quantile": 0.1, "values": [number, ...]},
    {"quantile": 0.5, "values": [number, ...]},
    {"quantile": 0.9, "values": [number, ...]}
  ],
  "metadata": {"model": "...", "device": "...", "inference_time_ms": ...}
}
```

The model emits a **fixed-window forecast** equal to `prediction_length`. The
*trading horizon* (which step a strategy reads) is decided downstream and
must satisfy `trading_horizon <= prediction_length`.

## Models (canonical registry)

Sourced from `shared/model_registry.py`. Working today:

| HuggingFace ID                              | Family   | Container                      | Port  |
|---------------------------------------------|----------|--------------------------------|-------|
| `amazon/chronos-t5-tiny`                    | chronos  | `forecast-chronos-t5-tiny`     | 12710 |
| `amazon/chronos-t5-mini`                    | chronos  | `forecast-chronos-t5-mini`     | 12711 |
| `amazon/chronos-t5-small`                   | chronos  | `forecast-chronos-t5-small`    | 12712 |
| `amazon/chronos-t5-base`                    | chronos  | `forecast-chronos-t5-base`     | 12713 |
| `amazon/chronos-t5-large`                   | chronos  | `forecast-chronos-t5-large`    | 12714 |
| `google/timesfm-2.0-500m-pytorch`           | timesfm  | `forecast-timesfm-2-0`         | 12721 |

Chronos Bolt is intentionally not shipped (incompatible model signature; broken).

## How to add a new model

1. **Register it.** Append a `ModelInfo(...)` row to `shared/model_registry.py`
   (the canonical checklist lives in that module's docstring).
2. **Add a compose service.** Copy an existing block in `docker-compose.yml`; change `MODEL_VARIANT` (chronos) or `TIMESFM20_DEFAULT_CHECKPOINT` (timesfm) and the host port.
3. **If it's a new family:** add `forecast/models/{family}/services/model.py` that
   exposes `initialize_model(model_variant, ...)`, `get_status() -> (status, error)`,
   `inference(...)`, and `shutdown_model()`. Mirror `chronos` or `timesfm20`. Add
   routes under `forecast/models/{family}/routes/endpoints.py` and include them
   from `forecast/main.py`.
4. **Refresh combinations.example.yaml** so the agent path picks it up.

## Configuration

| Env | Default | Notes |
|-----|---------|-------|
| `API_SECRET_KEY` | required | Bearer token |
| `MODEL_NAME` | `all` | `chronos`, `timesfm20`, or `all` (gateway) |
| `MODEL_VARIANT` | (chronos containers) | e.g. `amazon/chronos-t5-tiny` |
| `TIMESFM20_DEFAULT_CHECKPOINT` | `google/timesfm-2.0-500m-pytorch` | Used by TimesFM containers |
| `HF_HOME` | `/models_cache` | HuggingFace cache root inside the container |
| `MODELS_CACHE_PATH` | `./.models_cache` | Host bind mount |
| `DEVICE` | `cpu` | `cpu` \| `cuda:0` \| `mps` |
| `UVICORN_WORKERS` | `1` | **Hard-fail if not 1** (singleton state) |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | uvicorn bind |

## Limits & invariants

- **Single worker per process.** Forecast hard-fails at startup otherwise.
- **Container-per-model is the de facto sharding.** Cross-model concurrent
  runs already parallelize. Same-model requests serialize behind the lock.
- **Lazy initialization.** A container is "healthy" before any model is
  loaded. Call the family's `/initialization` to load weights; the agent
  path does this implicitly via the orchestrator's first inference call.

## Run locally

```bash
# All-in-one dev container (CPU)
docker compose up -d forecast forecast-chronos-t5-tiny

# Or the venv path (single-process):
uv pip install -e ".[forecasting]"
uvicorn forecast.main:app --host 0.0.0.0 --port 12700
```

## Tests

```bash
uv run pytest tests/forecast forecast/models
```
