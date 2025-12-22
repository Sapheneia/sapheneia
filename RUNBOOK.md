# Sapheneia Chronos Integration Runbook

## Table of Contents
1. [Quick Start](#quick-start)
2. [Service Architecture](#service-architecture)
3. [Starting Services](#starting-services)
4. [Stopping Services](#stopping-services)
5. [Health Checks](#health-checks)
6. [Debugging](#debugging)
7. [Common Issues](#common-issues)
8. [Testing](#testing)
9. [Logs](#logs)
10. [Performance Monitoring](#performance-monitoring)

---

## Quick Start

### Start Core Services + One Model
```bash
cd /Users/jin/PycharmProjects/sapheneia

# Start core services and one Chronos model
podman-compose up -d data forecast forecast-chronos-t5-tiny

# Wait for services to be ready (~15 seconds)
sleep 15

# Check health
curl http://localhost:8001/health  # Data service
curl http://localhost:8000/health  # Main forecast service
curl http://localhost:8100/health  # Chronos tiny

# Test from AleutianLocal
cd /Users/jin/GolandProjects/AleutianLocal
./aleutian stack start --profile local
./aleutian timeseries forecast SPY --model "amazon/chronos-t5-tiny" --context 90 --horizon 10
```

### Stop All Services
```bash
cd /Users/jin/PycharmProjects/sapheneia
podman-compose stop
```

---

## Service Architecture

### Core Services (Always Needed)
- **data** (`sapheneia-data`) - Finance data service (Yahoo Finance → InfluxDB)
  - Port: 8001 (external), 8000 (internal)
  - Container: `sapheneia-data`
  - Network: `aleutian-shared`

- **forecast** (`sapheneia-forecast`) - Main forecast API with TimesFM
  - Port: 8000 (external/internal)
  - Container: `sapheneia-forecast`
  - Includes: TimesFM-2.0, legacy endpoint

- **trading** (`sapheneia-trading`) - Trading strategies API
  - Port: 9000
  - Container: `sapheneia-trading`

- **ui** (`sapheneia-ui`) - Web interface
  - Port: 8080
  - Container: `sapheneia-ui`

### Chronos Model Containers (On-Demand)
Each Chronos model runs in its own container:

| Model | Container | External Port | Model Size |
|-------|-----------|---------------|------------|
| chronos-t5-tiny | `forecast-chronos-t5-tiny` | 8100 | 8M params |
| chronos-t5-mini | `forecast-chronos-t5-mini` | 8101 | 20M params |
| chronos-t5-small | `forecast-chronos-t5-small` | 8102 | 46M params |
| chronos-t5-base | `forecast-chronos-t5-base` | 8103 | 200M params |
| chronos-t5-large | `forecast-chronos-t5-large` | 8104 | 710M params |
| chronos-bolt-mini | `forecast-chronos-bolt-mini` | 8105 | Fast mini |
| chronos-bolt-small | `forecast-chronos-bolt-small` | 8106 | Fast small |
| chronos-bolt-base | `forecast-chronos-bolt-base` | 8107 | Fast base |

---

## Starting Services

### Option 1: Start Only What You Need (Recommended)
```bash
# Start minimal set for Chronos testing
podman-compose up -d data forecast-chronos-t5-tiny

# Add more models as needed
podman-compose up -d forecast-chronos-t5-mini forecast-chronos-t5-small
```

### Option 2: Start Core Services Only
```bash
# Start everything except Chronos models
podman-compose up -d forecast trading data ui
```

### Option 3: Start Everything
```bash
# Start all services (9 containers)
podman-compose up -d
```

### Option 4: Start Specific Model Variants
```bash
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

### Startup Verification
```bash
# Check all running containers
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Watch logs during startup
podman-compose logs -f forecast-chronos-t5-tiny

# Wait for "Application startup complete"
# Ctrl+C to stop watching
```

---

## Stopping Services

### Stop Specific Models
```bash
# Stop one model
podman-compose stop forecast-chronos-t5-tiny

# Stop multiple models
podman-compose stop forecast-chronos-t5-tiny forecast-chronos-t5-mini

# Stop all Chronos models
podman stop $(podman ps -q --filter "name=forecast-chronos")
```

### Stop All Services
```bash
# Stop all Sapheneia services
podman-compose stop

# Stop and remove containers (preserves volumes)
podman-compose down

# Stop, remove, and clean up volumes (WARNING: deletes data)
podman-compose down -v
```

---

## Health Checks

### Quick Health Check Script
```bash
#!/bin/bash
# save as: check-health.sh

echo "=== Sapheneia Health Check ==="
echo ""

# Data service
echo -n "Data Service: "
curl -s http://localhost:8001/health > /dev/null && echo "✅ UP" || echo "❌ DOWN"

# Main forecast service
echo -n "Forecast Service: "
curl -s http://localhost:8000/health > /dev/null && echo "✅ UP" || echo "❌ DOWN"

# Trading service
echo -n "Trading Service: "
curl -s http://localhost:9000/health > /dev/null && echo "✅ UP" || echo "❌ DOWN"

# UI
echo -n "UI: "
curl -s http://localhost:8080/health > /dev/null && echo "✅ UP" || echo "❌ DOWN"

# Chronos models
echo ""
echo "Chronos Models:"
for port in {8100..8107}; do
  model=$(curl -s http://localhost:${port}/health 2>/dev/null | jq -r '.service // empty')
  if [ -n "$model" ]; then
    echo "  Port ${port}: ✅ UP ($model)"
  fi
done
```

### Check Model Status
```bash
# Check if model is initialized
curl http://localhost:8100/forecast/v1/chronos/status \
  -H "Authorization: Bearer default_trading_api_key_please_change"

# Expected response:
# {
#   "model_status": "ready",  # or "uninitialized"
#   "model_variant": "amazon/chronos-t5-tiny",
#   "device": "cpu"
# }
```

### End-to-End Test
```bash
# Test legacy endpoint (what AleutianLocal uses)
curl -X POST http://localhost:8000/v1/timeseries/forecast \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer default_trading_api_key_please_change" \
  -d '{
    "name": "SPY",
    "context_period_size": 50,
    "forecast_period_size": 10,
    "model": "amazon/chronos-t5-tiny"
  }'

# Expected response:
# {
#   "name": "SPY",
#   "forecast": [450.2, 451.5, ...],
#   "message": "Success"
# }
```

---

## Debugging

### Step 1: Check Container Status
```bash
# List all containers
podman ps -a --filter "name=sapheneia" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check if container is running
podman ps --filter "name=forecast-chronos-t5-tiny"

# Check exit code if stopped
podman ps -a --filter "name=forecast-chronos-t5-tiny" --format "{{.Status}}"
```

### Step 2: Check Logs
```bash
# View last 50 lines
podman logs --tail 50 forecast-chronos-t5-tiny

# Follow logs in real-time
podman logs -f forecast-chronos-t5-tiny

# Search for errors
podman logs forecast-chronos-t5-tiny 2>&1 | grep -i error

# Search for specific model initialization
podman logs forecast-chronos-t5-tiny 2>&1 | grep "Chronos initialization"

# Check data service errors
podman logs sapheneia-data 2>&1 | grep "400"
```

### Step 3: Check Network Connectivity
```bash
# Verify network exists
podman network ls | grep aleutian-shared

# Create network if missing
podman network create aleutian-shared

# Check if container is on network
podman network inspect aleutian-shared | grep forecast-chronos-t5-tiny

# Test connectivity from one container to another
podman exec forecast-chronos-t5-tiny curl -s http://sapheneia-data:8000/health
```

### Step 4: Check Volume Mounts
```bash
# Verify code is mounted
podman exec forecast-chronos-t5-tiny ls -la /app/forecast/core/

# Check if legacy_service.py exists
podman exec forecast-chronos-t5-tiny cat /app/forecast/core/legacy_service.py | grep "data_service_url"

# Verify models cache
podman exec forecast-chronos-t5-tiny ls -la /models_cache/
```

### Step 5: Check Model Cache
```bash
# Verify model files exist
ls -la /Volumes/ai_models/aleutian_data/models_cache/ | grep chronos

# Check specific model
ls -la /Volumes/ai_models/aleutian_data/models_cache/models--amazon--chronos-t5-tiny/

# Verify cache is writable (HuggingFace needs to write lock files)
podman exec forecast-chronos-t5-tiny touch /models_cache/test.txt && \
  podman exec forecast-chronos-t5-tiny rm /models_cache/test.txt && \
  echo "✅ Cache is writable" || echo "❌ Cache is read-only"
```

### Step 6: Interactive Debugging
```bash
# Enter container shell
podman exec -it forecast-chronos-t5-tiny /bin/bash

# Inside container:
# - Check Python environment
python --version
pip list | grep chronos

# - Test imports
python -c "from forecast.core.legacy_service import LegacyForecastService; print('✅ Import successful')"

# - Check environment variables
env | grep -E "(API_PORT|MODEL_VARIANT|HF_HOME|DEVICE)"

# - Test internal API
curl http://localhost:8000/health
curl http://sapheneia-data:8000/health
```

### Step 7: Check API Authentication
```bash
# Test with correct auth
curl http://localhost:8100/forecast/v1/chronos/status \
  -H "Authorization: Bearer default_trading_api_key_please_change" \
  -v

# Look for: "< HTTP/1.1 200 OK"

# Test with wrong auth (should fail)
curl http://localhost:8100/forecast/v1/chronos/status \
  -H "Authorization: Bearer wrong_key" \
  -v

# Look for: "< HTTP/1.1 401 Unauthorized"
```

---

## Common Issues

### Issue 1: Container Won't Start
**Symptoms:**
```bash
podman ps -a | grep forecast-chronos-t5-tiny
# Shows: Exited (1) 2 minutes ago
```

**Debug:**
```bash
# Check logs for startup errors
podman logs forecast-chronos-t5-tiny

# Common errors:
# - "ModuleNotFoundError" → Rebuild image
# - "Port already in use" → Stop conflicting container
# - "Network not found" → Create aleutian-shared network
```

**Fix:**
```bash
# Rebuild and restart
podman-compose build forecast-chronos-t5-tiny
podman-compose up -d forecast-chronos-t5-tiny
```

### Issue 2: Model Initialization Fails
**Symptoms:**
```bash
curl http://localhost:8100/forecast/v1/chronos/status \
  -H "Authorization: Bearer default_trading_api_key_please_change"
# Returns: {"model_status": "error"}
```

**Debug:**
```bash
# Check initialization logs
podman logs forecast-chronos-t5-tiny 2>&1 | grep "initialization"

# Common errors:
# - "No such file or directory" → Model cache not mounted
# - "Read-only file system" → Cache needs write access
# - "CUDA out of memory" → Using GPU with insufficient memory
```

**Fix:**
```bash
# Verify cache is mounted and writable
podman exec forecast-chronos-t5-tiny ls -la /models_cache/

# Restart container
podman-compose restart forecast-chronos-t5-tiny

# Re-initialize model
curl -X POST http://localhost:8100/forecast/v1/chronos/initialization \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer default_trading_api_key_please_change" \
  -d '{"model_variant": "amazon/chronos-t5-tiny"}'
```

### Issue 3: Data Service Returns 400
**Symptoms:**
```bash
podman logs forecast-chronos-t5-tiny 2>&1 | grep "400 Bad Request"
# Shows: Client error '400 Bad Request' for url 'http://sapheneia-data:8000/v1/data/query'
```

**Debug:**
```bash
# Check data service logs
podman logs sapheneia-data 2>&1 | tail -20

# Test data service directly
curl -X POST http://localhost:8001/v1/data/query \
  -H "Content-Type: application/json" \
  -d '{"ticker": "SPY", "days": 90}'
```

**Fix:**
```bash
# Ensure data exists in InfluxDB
cd /Users/jin/GolandProjects/AleutianLocal
./aleutian timeseries fetch SPY --days 1800

# Restart data service
podman-compose restart data
```

### Issue 4: AleutianLocal Can't Connect
**Symptoms:**
```bash
./aleutian timeseries forecast SPY --model "amazon/chronos-t5-tiny" --context 90 --horizon 10
# Returns: connection refused or timeout
```

**Debug:**
```bash
# Check if container is on correct network
podman network inspect aleutian-shared | grep forecast-chronos-t5-tiny

# Test from AleutianLocal orchestrator
podman exec aleutian-go-orchestrator curl -s http://forecast-chronos-t5-tiny:8000/health
```

**Fix:**
```bash
# Restart both services
podman-compose restart forecast-chronos-t5-tiny
podman restart aleutian-go-orchestrator
```

### Issue 5: Old Code Running After Update
**Symptoms:**
- Made code changes but container still uses old code
- Error messages show old URLs or logic

**Debug:**
```bash
# Check if file is updated on host
grep "data_service_url" /Users/jin/PycharmProjects/sapheneia/forecast/core/legacy_service.py

# Check if container sees new code
podman exec forecast-chronos-t5-tiny grep "data_service_url" /app/forecast/core/legacy_service.py
```

**Fix:**
```bash
# Python modules are cached - must restart
podman-compose restart forecast-chronos-t5-tiny

# If that doesn't work, rebuild
podman-compose build forecast-chronos-t5-tiny
podman-compose up -d forecast-chronos-t5-tiny
```

---

## Testing

### Unit Tests
```bash
cd /Users/jin/PycharmProjects/sapheneia

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=forecast/core --cov-report=html

# Run specific test file
pytest tests/test_legacy_adapters.py -v

# Run specific test
pytest tests/test_legacy_adapters.py::test_determine_model_family -v
```

### Integration Tests
```bash
# Test direct Chronos API
./tests/integration/test_chronos_api.sh

# Test legacy endpoint
./tests/integration/test_legacy_endpoint.sh

# Test via AleutianLocal
./tests/integration/test_aleutian_integration.sh
```

### Manual Smoke Test
```bash
# 1. Start services
podman-compose up -d data forecast-chronos-t5-tiny

# 2. Wait for ready
sleep 15

# 3. Test health
curl http://localhost:8100/health

# 4. Test initialization
curl -X POST http://localhost:8100/forecast/v1/chronos/initialization \
  -H "Authorization: Bearer default_trading_api_key_please_change" \
  -d '{}'

# 5. Test inference
curl -X POST http://localhost:8100/forecast/v1/chronos/inference \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer default_trading_api_key_please_change" \
  -d '{
    "context": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "prediction_length": 5,
    "num_samples": 20
  }'

# 6. Test legacy endpoint
curl -X POST http://localhost:8000/v1/timeseries/forecast \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer default_trading_api_key_please_change" \
  -d '{
    "name": "SPY",
    "context_period_size": 50,
    "forecast_period_size": 10,
    "model": "amazon/chronos-t5-tiny"
  }'

# 7. Test from AleutianLocal
cd /Users/jin/GolandProjects/AleutianLocal
./aleutian timeseries forecast SPY --model "amazon/chronos-t5-tiny" --context 90 --horizon 10
```

---

## Logs

### Log Locations
```bash
# Container logs (stdout/stderr)
podman logs <container_name>

# Application logs (if written to files)
ls -la /Users/jin/PycharmProjects/sapheneia/logs/

# Inside containers
podman exec <container_name> ls -la /app/logs/
```

### Useful Log Commands
```bash
# Follow logs with timestamps
podman logs -f --timestamps forecast-chronos-t5-tiny

# Last 100 lines
podman logs --tail 100 forecast-chronos-t5-tiny

# Since specific time
podman logs --since 2025-12-21T17:00:00 forecast-chronos-t5-tiny

# Filter for errors
podman logs forecast-chronos-t5-tiny 2>&1 | grep -i error

# Search across all forecast containers
for container in $(podman ps --filter "name=forecast" --format "{{.Names}}"); do
  echo "=== $container ==="
  podman logs --tail 5 $container 2>&1 | grep -i error
done
```

### Log Aggregation
```bash
# View all Sapheneia logs together
podman-compose logs -f

# Filter specific services
podman-compose logs -f data forecast-chronos-t5-tiny

# Save logs to file
podman logs forecast-chronos-t5-tiny > chronos-tiny-logs.txt 2>&1
```

---

## Performance Monitoring

### Resource Usage
```bash
# Real-time stats for all containers
podman stats

# Stats for specific container
podman stats forecast-chronos-t5-tiny

# One-time snapshot
podman stats --no-stream
```

### Model Performance
```bash
# Check inference time in logs
podman logs forecast-chronos-t5-tiny 2>&1 | grep "inference_time_seconds"

# Example output:
# "inference_time_seconds": 2.45
```

### Memory Usage
```bash
# Check container memory
podman stats forecast-chronos-t5-tiny --no-stream --format "{{.MemUsage}}"

# Check model size
ls -lh /Volumes/ai_models/aleutian_data/models_cache/models--amazon--chronos-t5-tiny/
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Check disk space: `df -h /Volumes/ai_models/`
- Review error logs: `podman logs <container> 2>&1 | grep -i error`

**Weekly:**
- Restart containers to clear memory leaks: `podman-compose restart`
- Update models cache (if needed)
- Review performance metrics

**Monthly:**
- Rebuild images with latest dependencies: `podman-compose build`
- Clean unused containers: `podman container prune`
- Clean unused images: `podman image prune`

### Backup
```bash
# Backup model cache (if not already backed up)
rsync -av /Volumes/ai_models/aleutian_data/models_cache/ /path/to/backup/

# Backup configuration
cp docker-compose.yml docker-compose.yml.backup
cp .env .env.backup
```

---

## Quick Reference

### Common Commands Cheat Sheet
```bash
# Start minimal set
podman-compose up -d data forecast-chronos-t5-tiny

# Check status
podman ps --filter "name=forecast"

# View logs
podman logs -f forecast-chronos-t5-tiny

# Stop
podman-compose stop forecast-chronos-t5-tiny

# Restart
podman-compose restart forecast-chronos-t5-tiny

# Rebuild
podman-compose build forecast-chronos-t5-tiny
podman-compose up -d forecast-chronos-t5-tiny

# Test
curl http://localhost:8100/health
```

### Port Reference
- 8000 - Main forecast API
- 8001 - Data service (external)
- 8080 - UI
- 8100-8107 - Chronos models
- 9000 - Trading API

### Key Files
- `/Users/jin/PycharmProjects/sapheneia/docker-compose.yml` - Service definitions
- `/Users/jin/PycharmProjects/sapheneia/forecast/core/legacy_service.py` - Multi-model integration
- `/Users/jin/PycharmProjects/sapheneia/forecast/core/legacy_adapters.py` - Data transformations
- `/Users/jin/PycharmProjects/sapheneia/forecast/core/legacy_schema.py` - API contracts
- `/Users/jin/PycharmProjects/sapheneia/MODELS.md` - Model management guide
