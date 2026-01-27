# Sapheneia Forecasting Models Quick Reference

This guide provides quick commands for managing forecasting models in Sapheneia.

## Available Models

### Amazon Chronos Models

| Model ID | Container Name | Port | Description |
|----------|----------------|------|-------------|
| `amazon/chronos-t5-tiny` | `forecast-chronos-t5-tiny` | 8100 | Smallest T5-based model (fastest) |
| `amazon/chronos-t5-mini` | `forecast-chronos-t5-mini` | 8101 | Small T5-based model |
| `amazon/chronos-t5-small` | `forecast-chronos-t5-small` | 8102 | Medium T5-based model |
| `amazon/chronos-t5-base` | `forecast-chronos-t5-base` | 8103 | Base T5-based model |
| `amazon/chronos-t5-large` | `forecast-chronos-t5-large` | 8104 | Large T5-based model |
| `amazon/chronos-bolt-mini` | `forecast-chronos-bolt-mini` | 8105 | Fast mini model (Bolt) |
| `amazon/chronos-bolt-small` | `forecast-chronos-bolt-small` | 8106 | Fast small model (Bolt) |
| `amazon/chronos-bolt-base` | `forecast-chronos-bolt-base` | 8107 | Fast base model (Bolt) |

### Google TimesFM Models

| Model ID | Container Name | Port | Description |
|----------|----------------|------|-------------|
| `google/timesfm-2.0-500m-pytorch` | `forecast` | 8000 | TimesFM 2.0 500M parameter model |

## Starting Models

### Start Individual Chronos Models

```bash
# Start specific model
podman-compose up -d forecast-chronos-t5-tiny   # Smallest, fastest
podman-compose up -d forecast-chronos-t5-mini   # Small
podman-compose up -d forecast-chronos-t5-small  # Medium
podman-compose up -d forecast-chronos-t5-base   # Base
podman-compose up -d forecast-chronos-t5-large  # Large

# Bolt models (optimized for speed)
podman-compose up -d forecast-chronos-bolt-mini  # Fast mini
podman-compose up -d forecast-chronos-bolt-small # Fast small
podman-compose up -d forecast-chronos-bolt-base  # Fast base
```

### Start Multiple Models

```bash
# Start several models at once
podman-compose up -d \
  forecast-chronos-t5-tiny \
  forecast-chronos-t5-mini \
  forecast-chronos-t5-small

# Start all T5 models
podman-compose up -d \
  forecast-chronos-t5-tiny \
  forecast-chronos-t5-mini \
  forecast-chronos-t5-small \
  forecast-chronos-t5-base \
  forecast-chronos-t5-large

# Start all Bolt models
podman-compose up -d \
  forecast-chronos-bolt-mini \
  forecast-chronos-bolt-small \
  forecast-chronos-bolt-base
```

### Start Core Services

```bash
# Start core Sapheneia services (forecast, trading, data, ui)
podman-compose up -d
```

This will start:
- `forecast` (main API with TimesFM)
- `trading` (trading strategies API)
- `data` (finance data service)
- `ui` (web interface)

Chronos models will NOT auto-start - you must start them explicitly.

## Viewing Running Models

```bash
# View all Chronos containers
podman ps --filter "name=forecast-chronos"

# View all Sapheneia containers
podman ps --filter "name=sapheneia"

# View all forecast-related containers
podman ps --filter "name=forecast"
```

## Stopping Models

```bash
# Stop specific model
podman-compose stop forecast-chronos-t5-tiny

# Stop multiple models
podman-compose stop \
  forecast-chronos-t5-tiny \
  forecast-chronos-t5-mini

# Stop all Chronos models
podman stop $(podman ps -q --filter "name=forecast-chronos")

# Stop all Sapheneia services
podman-compose down
```

## Viewing Logs

```bash
# View logs for specific model
podman logs forecast-chronos-t5-tiny

# Follow logs in real-time
podman logs -f forecast-chronos-t5-tiny

# View last 100 lines
podman logs --tail 100 forecast-chronos-t5-tiny
```

## Testing Models

### Direct API Test

```bash
# Check health
curl http://localhost:8100/health

# Initialize model
curl -X POST http://localhost:8100/forecast/v1/chronos/initialization \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer default_trading_api_key_please_change" \
  -d '{}'

# Check status
curl http://localhost:8100/forecast/v1/chronos/status \
  -H "Authorization: Bearer default_trading_api_key_please_change"

# Run inference
curl -X POST http://localhost:8100/forecast/v1/chronos/inference \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer default_trading_api_key_please_change" \
  -d '{
    "context": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
    "prediction_length": 5,
    "num_samples": 20
  }'
```

### Test via AleutianLocal

```bash
# Fetch SPY data
./aleutian timeseries fetch SPY --days 1800

# Run forecast
./aleutian timeseries forecast SPY \
  --model "amazon/chronos-t5-tiny" \
  --context 90 \
  --horizon 10

# Run full evaluation
./aleutian evaluate run \
  --ticker SPY \
  --config strategies/spy_chronos_tiny_v1.yaml
```

## Rebuilding Containers

```bash
# Rebuild specific model container
podman-compose build forecast-chronos-t5-tiny

# Rebuild and restart
podman-compose up -d --build forecast-chronos-t5-tiny

# Rebuild all Chronos containers
podman-compose build \
  forecast-chronos-t5-tiny \
  forecast-chronos-t5-mini \
  forecast-chronos-t5-small \
  forecast-chronos-t5-base \
  forecast-chronos-t5-large \
  forecast-chronos-bolt-mini \
  forecast-chronos-bolt-small \
  forecast-chronos-bolt-base
```

## Resource Management

### Check Container Resources

```bash
# View resource usage
podman stats

# View specific container stats
podman stats forecast-chronos-t5-tiny
```

### Model Loading Behavior

Each Chronos container:
- Loads one model variant from `/Volumes/ai_models/aleutian_data/models_cache/`
- Uses CPU by default (can be changed to `DEVICE=cuda` for GPU)
- Shares the read-only models cache (no duplication)
- Runs independently on its own port

**Recommended approach:**
- Start with 1-2 models for testing
- Add more as needed for specific evaluations
- Stop unused containers to free resources

## Troubleshooting

### Container won't start

```bash
# Check logs
podman logs forecast-chronos-t5-tiny

# Verify network exists
podman network ls | grep aleutian-shared

# Create network if missing
podman network create aleutian-shared

# Verify models cache
ls -la /Volumes/ai_models/aleutian_data/models_cache/
```

### Model initialization fails

```bash
# Check if model files exist
podman exec forecast-chronos-t5-tiny \
  ls -la /models_cache/models--amazon--chronos-t5-tiny

# Check HF_HOME environment variable
podman exec forecast-chronos-t5-tiny env | grep HF_HOME

# Check container can write to cache (for lock files)
podman exec forecast-chronos-t5-tiny \
  touch /models_cache/test.txt && rm /models_cache/test.txt
```

### AleutianLocal can't connect

```bash
# Verify container is on correct network
podman network inspect aleutian-shared | grep forecast-chronos-t5-tiny

# Test from host
curl http://localhost:8100/health

# Test from AleutianLocal orchestrator
podman exec aleutian-go-orchestrator \
  curl -s http://forecast-chronos-t5-tiny:8000/health
```

## Model Cache Location

All models are pre-downloaded to:
```
/Volumes/ai_models/aleutian_data/models_cache/
├── models--amazon--chronos-t5-tiny/
├── models--amazon--chronos-t5-mini/
├── models--amazon--chronos-t5-small/
├── models--amazon--chronos-t5-base/
├── models--amazon--chronos-t5-large/
├── models--amazon--chronos-bolt-mini/
├── models--amazon--chronos-bolt-small/
└── models--amazon--chronos-bolt-base/
```

Mounted to containers at: `/models_cache`

## Integration with AleutianLocal

AleutianLocal's `timeseries.go` automatically routes to the correct container based on model name:

- `amazon/chronos-t5-tiny` → `http://forecast-chronos-t5-tiny:8000`
- `amazon/chronos-t5-mini` → `http://forecast-chronos-t5-mini:8000`
- `amazon/chronos-t5-small` → `http://forecast-chronos-t5-small:8000`
- etc.

No configuration changes needed in AleutianLocal!

## Next Steps

1. **Test with smallest model first**: `forecast-chronos-t5-tiny`
2. **Compare with TimesFM**: Run same evaluation with both models
3. **Benchmark different variants**: Test various model sizes
4. **Scale up**: Add more models as needed for your workflows
