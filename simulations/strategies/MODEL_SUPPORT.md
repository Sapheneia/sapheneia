# Model Support Status

This document tracks which forecast models work with AleutianFOSS + Sapheneia.

## Quick Reference

| Model Family | Status | Working Models | Notes |
|-------------|--------|----------------|-------|
| Chronos T5 | **WORKING** | tiny, mini, small, base, large | Fully tested |
| Chronos Bolt | **UNTESTED** | mini, small, base | May not work - needs testing |
| TimesFM | **PARTIAL** | 2.0 only | Container commented out |
| Moirai | **NOT IMPLEMENTED** | - | No Sapheneia support |
| Granite | **NOT IMPLEMENTED** | - | No Sapheneia support |
| Moment | **NOT IMPLEMENTED** | - | No Sapheneia support |
| Others | **NOT IMPLEMENTED** | - | No Sapheneia support |

---

## Supported Models (Sapheneia Implementation Exists)

### Amazon Chronos T5 Series - WORKING

| Slug | HuggingFace ID | Port | Strategy Example |
|------|----------------|------|------------------|
| `chronos-t5-tiny` | amazon/chronos-t5-tiny | 12710 | `SPY/spy_chronos_tiny.yaml` |
| `chronos-t5-mini` | amazon/chronos-t5-mini | 12711 | - |
| `chronos-t5-small` | amazon/chronos-t5-small | 12712 | - |
| `chronos-t5-base` | amazon/chronos-t5-base | 12713 | `SPY/spy_chronos_base.yaml` |
| `chronos-t5-large` | amazon/chronos-t5-large | 12714 | - |

**Test Commands:**
```bash
# 1. Start and initialize the model
./scripts/model-manager.sh start chronos-t5-tiny
./scripts/model-manager.sh init chronos-t5-tiny

# 2. Run a backtest
aleutian evaluate run --config simulations/strategies/SPY/spy_chronos_tiny.yaml --api-version unified
```

### Amazon Chronos Bolt Series - NEEDS TESTING

These are defined in docker-compose but may have issues with the ChronosPipeline loader.

| Slug | HuggingFace ID | Port | Status |
|------|----------------|------|--------|
| `chronos-bolt-mini` | amazon/chronos-bolt-mini | 12715 | **NEEDS TESTING** |
| `chronos-bolt-small` | amazon/chronos-bolt-small | 12716 | **NEEDS TESTING** |
| `chronos-bolt-base` | amazon/chronos-bolt-base | 12717 | **NEEDS TESTING** |

**Issue:** Test file has comment `# Marked as broken` for chronos-bolt-mini.

**Test Commands:**
```bash
# Test if Bolt models work
./scripts/model-manager.sh start chronos-bolt-mini
./scripts/model-manager.sh init chronos-bolt-mini

# Check status
curl http://localhost:12715/forecast/v1/chronos/status

# If ready, try a backtest
aleutian evaluate run --config simulations/strategies/SPY/spy_chronos_bolt.yaml --api-version unified
```

### Google TimesFM - PARTIAL

TimesFM is implemented but container is commented out in docker-compose.yml.

| Slug | HuggingFace ID | Port | Status |
|------|----------------|------|--------|
| `timesfm-2-0` | google/timesfm-2.0-500m-pytorch | 12720 | Implemented, needs uncomment |

**To Enable:**
1. Edit `docker-compose.yml`
2. Uncomment the `forecast-timesfm-2-0` service section
3. Start the container

---

## NOT Implemented (In AleutianFOSS Routing But No Sapheneia Support)

These models are listed in AleutianFOSS `timeseries.go` routing but have **no Sapheneia implementation**.
Running backtests with these will fail.

### Salesforce Moirai
- `moirai-1-0-small`
- `moirai-1-1-small`, `moirai-1-1-base`, `moirai-1-1-large`
- `moirai-2-0-small`

### IBM Granite
- `granite-ttm-r1`, `granite-ttm-r2`
- `granite-flowstate`, `granite-patchtsmixer`, `granite-patchtst`

### AutonLab Moment
- `moment-small`, `moment-base`, `moment-large`

### Alibaba Yinglong
- `yinglong-6m`, `yinglong-50m`, `yinglong-110m`, `yinglong-300m`

### Others
- `lag-llama`, `kairos-10m`, `kairos-50m`
- `timemoe-200m`, `timer`, `sundial`, `toto`
- `falcon-tst`, `tempopfn`, `forecastpfn`
- `chattime`, `opencity`, `units`

---

## Testing Procedure

### Pre-flight Check

```bash
# 1. Check what images are built
podman images | grep forecast

# 2. Check what containers are running
podman ps | grep forecast

# 3. List all models and status
./scripts/model-manager.sh list
```

### Test Chronos T5 Series (Known Working)

```bash
# Start smallest model first
./scripts/model-manager.sh start chronos-t5-tiny
./scripts/model-manager.sh init chronos-t5-tiny

# Verify it's ready
curl http://localhost:12710/forecast/v1/chronos/status

# Run test backtest
aleutian evaluate run \
  --config simulations/strategies/SPY/spy_chronos_tiny.yaml \
  --api-version unified

# Export results
aleutian evaluate export <RUN_ID>
```

### Test Chronos Bolt Series (Unknown Status)

```bash
# Try Bolt mini
./scripts/model-manager.sh start chronos-bolt-mini
./scripts/model-manager.sh init chronos-bolt-mini

# Check if initialization succeeded
curl http://localhost:12715/forecast/v1/chronos/status

# If status shows "ready", try backtest
aleutian evaluate run \
  --config simulations/strategies/SPY/spy_chronos_bolt.yaml \
  --api-version unified
```

### Test TimesFM (Requires Manual Enable)

```bash
# 1. Edit docker-compose.yml to uncomment forecast-timesfm-2-0

# 2. Start the container
podman-compose up -d forecast-timesfm-2-0

# 3. Initialize
curl -X POST http://localhost:12720/forecast/v1/timesfm20/initialization \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer default_trading_api_key_please_change" \
  -d '{}'

# 4. Run backtest
aleutian evaluate run \
  --config simulations/strategies/SPY/spy_timesfm.yaml \
  --api-version unified
```

---

## Known Issues

### 1. Chronos Bolt Models
- **Issue:** May fail to initialize
- **Reason:** ChronosPipeline might not support Bolt models the same way as T5
- **Status:** Needs testing to confirm

### 2. TimesFM Container Commented Out
- **Issue:** Container won't start by default
- **Solution:** Uncomment in docker-compose.yml

### 3. Most Models Not Implemented
- **Issue:** AleutianFOSS routes to containers that don't exist
- **Error:** Connection refused to `http://forecast-<model>:8000`
- **Solution:** Need Sapheneia implementations for each model family

---

## Adding Support for New Models

To add a new model family to Sapheneia:

1. **Create module structure:**
   ```
   forecast/models/<family>/
   ├── __init__.py
   ├── routes/
   │   └── endpoints.py
   ├── services/
   │   └── model.py
   └── schemas/
       └── schema.py
   ```

2. **Register in MODEL_REGISTRY:**
   Edit `forecast/models/__init__.py`

3. **Add to Dockerfile.forecast:**
   Add conditional dependency installation

4. **Add to docker-compose.yml:**
   Create service definition

5. **Test thoroughly**

---

## Environment Variables

```bash
# Required for backtests
export ORCHESTRATOR_URL=http://localhost:12700
export SAPHENEIA_API_KEY=default_trading_api_key_please_change

# Optional: GPU support
export DEVICE=cuda  # or cpu, mps

# Optional: Model cache location
export MODELS_CACHE_PATH=/path/to/models_cache
```
