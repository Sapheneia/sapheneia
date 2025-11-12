# Phase 6 Testing Guide - Deployment Configuration

This guide provides step-by-step instructions to test the Phase 6 implementation.

## Prerequisites

- ✅ Docker installed and running
- ✅ `.env` file exists (or will be created during init)
- ✅ `TRADING_API_KEY` set in `.env` (min 32 characters for production)

## Test Checklist

### 1. Help System Tests

#### Test 1.1: General Help
```bash
./setup.sh --help
```
**Expected**: Shows overview of both applications (forecast and trading)

#### Test 1.2: Forecast-Specific Help
```bash
./setup.sh --help forecast
```
**Expected**: Shows forecast application help with ports 8000 and 8080

#### Test 1.3: Trading-Specific Help
```bash
./setup.sh --help trading
```
**Expected**: Shows trading application help with port 9000

---

### 2. Backward Compatibility Tests

#### Test 2.1: Old "all" Command (Should Error)
```bash
./setup.sh run-venv all
```
**Expected**: Error message suggesting `./setup.sh run-venv forecast all`

#### Test 2.2: Init Without Application (Should Default to Forecast)
```bash
./setup.sh init
```
**Expected**: Initializes forecast application (backward compatible)

#### Test 2.3: Stop Without Application (Should Error)
```bash
./setup.sh stop
```
**Expected**: Error message requiring application name

---

### 3. Forecast Application Tests

#### Test 3.1: Initialize Forecast Application
```bash
./setup.sh init forecast
```
**Expected**: 
- Creates `.venv` if not exists
- Installs dependencies
- Creates directories: `api/models/timesfm20/local`, `data/uploads`, `data/results`, `logs`
- Shows next steps for forecast application

#### Test 3.2: Run Forecast API (venv)
```bash
./setup.sh run-venv forecast api
```
**Expected**:
- Starts API server on port 8000
- Shows health and docs URLs
- Verify: `curl http://localhost:8000/health` returns 200

#### Test 3.3: Run Forecast UI (venv)
```bash
./setup.sh run-venv forecast ui
```
**Expected**:
- Starts UI server on port 8080
- Verify: `curl http://localhost:8080/health` returns 200

#### Test 3.4: Run Forecast All Services (venv)
```bash
./setup.sh run-venv forecast all
```
**Expected**:
- Starts both API (8000) and UI (8080)
- Shows URLs for both services

#### Test 3.5: Stop Forecast Services
```bash
./setup.sh stop forecast
```
**Expected**:
- Stops API and UI processes
- Kills ports 8000 and 8080
- Stops Docker containers if running

---

### 4. Trading Application Tests

#### Test 4.1: Initialize Trading Application
```bash
./setup.sh init trading
```
**Expected**:
- Creates `.venv` if not exists (reuses if already exists)
- Installs dependencies
- Creates `logs` directory
- Shows next steps for trading application

#### Test 4.2: Run Trading Service (venv)
```bash
./setup.sh run-venv trading
```
**Expected**:
- Starts trading API server on port 9000
- Shows health and docs URLs
- Verify: `curl http://localhost:9000/health` returns 200
- Verify: `curl http://localhost:9000/trading/strategies` returns 200 (no auth required)

#### Test 4.3: Test Trading API Endpoints
```bash
# Health check (no auth required)
curl http://localhost:9000/health

# Strategies list (no auth required)
curl http://localhost:9000/trading/strategies

# Execute endpoint (requires auth)
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
    "execution_size": 10.0
  }'
```
**Expected**: Returns trading signal response

#### Test 4.4: Stop Trading Services
```bash
./setup.sh stop trading
```
**Expected**:
- Stops trading process
- Kills port 9000
- Stops Docker container if running

---

### 5. Docker Tests

#### Test 5.1: Build Trading Docker Image
```bash
docker build -f Dockerfile.trading -t sapheneia-trading .
```
**Expected**:
- Builds successfully
- Image tagged as `sapheneia-trading`
- No build errors

#### Test 5.2: Run Trading Container (Manual)
```bash
docker run -d \
  --name sapheneia-trading-test \
  -p 9000:9000 \
  -e TRADING_API_KEY="test_key_32_chars_minimum_length_required" \
  -e TRADING_API_HOST=0.0.0.0 \
  -e TRADING_API_PORT=9000 \
  -e LOG_LEVEL=INFO \
  -e ENVIRONMENT=development \
  sapheneia-trading
```
**Expected**:
- Container starts successfully
- Health check passes after 40 seconds
- Verify: `curl http://localhost:9000/health` returns 200

#### Test 5.3: Clean Up Test Container
```bash
docker stop sapheneia-trading-test
docker rm sapheneia-trading-test
```

#### Test 5.4: Run Trading with Docker Compose (via setup.sh)
```bash
./setup.sh run-docker trading
```
**Expected**:
- Builds and starts trading container
- Container name: `sapheneia-trading`
- Port mapping: 9000:9000
- Verify: `curl http://localhost:9000/health` returns 200

#### Test 5.5: Verify Docker Compose Service
```bash
docker compose ps trading
```
**Expected**: Shows trading service running

#### Test 5.6: View Trading Container Logs
```bash
docker compose logs trading
```
**Expected**: Shows trading API startup logs

#### Test 5.7: Stop Trading Container
```bash
./setup.sh stop trading
```
**Expected**: Stops and removes trading container

---

### 6. Docker Compose Integration Tests

#### Test 6.1: Run All Forecast Services with Docker
```bash
./setup.sh run-docker forecast all
```
**Expected**:
- Starts `sapheneia-api` and `sapheneia-ui` containers
- Both services healthy
- API on port 8000, UI on port 8080

#### Test 6.2: Run Trading with Forecast (Separate)
```bash
# Start forecast services
./setup.sh run-docker forecast all

# Start trading service
./setup.sh run-docker trading
```
**Expected**:
- All three services running independently
- No port conflicts
- All services accessible on their respective ports

#### Test 6.3: Verify All Services Running
```bash
docker compose ps
```
**Expected**: Shows api, ui, and trading services all running

#### Test 6.4: Test Service Isolation
```bash
# Test forecast API
curl http://localhost:8000/health

# Test forecast UI
curl http://localhost:8080/health

# Test trading API
curl http://localhost:9000/health
```
**Expected**: All three services respond independently

---

### 7. Error Handling Tests

#### Test 7.1: Invalid Application Name
```bash
./setup.sh init invalid
```
**Expected**: Error message with valid options

#### Test 7.2: Invalid Service Name for Forecast
```bash
./setup.sh run-venv forecast invalid
```
**Expected**: Error message with valid services (api, ui, all)

#### Test 7.3: Missing Application for Stop
```bash
./setup.sh stop
```
**Expected**: Error message requiring application name

#### Test 7.4: Old "all" Command
```bash
./setup.sh run-venv all
```
**Expected**: Error suggesting `./setup.sh run-venv forecast all`

---

### 8. Port Conflict Tests

#### Test 8.1: Port Already in Use
```bash
# Start trading service
./setup.sh run-venv trading

# Try to start again (should handle gracefully)
./setup.sh run-venv trading
```
**Expected**: Script kills existing process on port 9000 and starts new one

---

### 9. Environment Variable Tests

#### Test 9.1: Trading API Key Validation
```bash
# Set short API key in .env
export TRADING_API_KEY="short"

# Start trading service
./setup.sh run-venv trading
```
**Expected**: 
- In development: Warning but allows short key
- In production: Should enforce 32+ character requirement

---

### 10. Health Check Tests

#### Test 10.1: Trading Health Endpoint
```bash
curl http://localhost:9000/health
```
**Expected**: Returns JSON with status "healthy" and available strategies

#### Test 10.2: Trading Root Endpoint
```bash
curl http://localhost:9000/
```
**Expected**: Returns JSON with status "ok" and service info

---

## Quick Test Script

Run this script to test all major functionality:

```bash
#!/bin/bash
set -e

echo "=== Phase 6 Testing ==="

# Test help system
echo "1. Testing help system..."
./setup.sh --help > /dev/null && echo "✅ General help works"
./setup.sh --help forecast > /dev/null && echo "✅ Forecast help works"
./setup.sh --help trading > /dev/null && echo "✅ Trading help works"

# Test backward compatibility
echo "2. Testing backward compatibility..."
./setup.sh init > /dev/null 2>&1 && echo "✅ Init defaults to forecast"

# Test error handling
echo "3. Testing error handling..."
./setup.sh stop 2>&1 | grep -q "Application name required" && echo "✅ Stop requires application name"

# Test Docker build
echo "4. Testing Docker build..."
if docker build -f Dockerfile.trading -t sapheneia-trading-test . > /dev/null 2>&1; then
    echo "✅ Dockerfile.trading builds successfully"
    docker rmi sapheneia-trading-test > /dev/null 2>&1
else
    echo "❌ Dockerfile.trading build failed"
fi

# Test docker-compose configuration
echo "5. Testing docker-compose..."
if docker compose config > /dev/null 2>&1; then
    echo "✅ docker-compose.yml is valid"
else
    echo "❌ docker-compose.yml has errors"
fi

echo "=== Testing Complete ==="
```

---

## Expected Results Summary

✅ **All tests should pass** if Phase 6 is correctly implemented:

- Help system works for all three modes (general, forecast, trading)
- Backward compatibility maintained for `init` command
- Error messages guide users to correct syntax
- Forecast application works with new command structure
- Trading application works independently
- Docker build succeeds
- Docker Compose integration works
- Services run on correct ports (8000, 8080, 9000)
- Health checks pass
- Service isolation maintained

---

## Troubleshooting

### Issue: Port already in use
**Solution**: Run `./setup.sh stop [forecast|trading]` first

### Issue: Docker build fails
**Solution**: Check that `pyproject.toml` and `trading/` directory exist

### Issue: Container won't start
**Solution**: Check `.env` file has `TRADING_API_KEY` set (min 32 chars)

### Issue: Health check fails
**Solution**: Wait 40 seconds for container to fully start, then check logs

---

## Next Steps

After successful testing:
1. ✅ Phase 6 implementation verified
2. ⏭️ Proceed to Phase 7: Documentation
3. ⏭️ Proceed to Phase 8: Integration & Polish

