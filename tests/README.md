# Sapheneia Test Suite

Comprehensive unit tests for the Chronos multi-model integration refactor.

## Coverage Target: 90%+

This test suite achieves 90%+ code coverage for:
- `forecast/core/legacy_schema.py` - Pydantic data contracts
- `forecast/core/legacy_adapters.py` - Pure transformation functions
- `forecast/core/legacy_service.py` - Service orchestration layer

## Quick Start

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests with coverage
./run_tests.sh

# Quick test run (no coverage)
./run_tests.sh --quick

# View coverage report
open htmlcov/index.html
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest configuration & fixtures
├── README.md               # This file
└── core/
    ├── __init__.py
    ├── test_legacy_schema.py      # Pydantic model validation tests
    ├── test_legacy_adapters.py    # Pure function transformation tests
    └── test_legacy_service.py     # Service layer tests with mocks
```

## Test Files

### test_legacy_schema.py
Tests Pydantic model validation for all data contracts:
- `AleutianForecastRequest` - Request from AleutianLocal
- `AleutianForecastResponse` - Response to AleutianLocal
- `ChronosInferenceRequest` - Chronos model inference request
- `ChronosInferenceResponse` - Chronos model inference response

**Coverage:**
- Valid model creation
- Required field validation
- Field type validation
- Constraint validation (gt=0, le=1.0, etc.)
- Default values
- JSON schema examples
- Cross-model consistency

### test_legacy_adapters.py
Tests pure transformation functions:
- `determine_model_family()` - Model type detection
- `get_model_base_path()` - API endpoint routing
- `aleutian_to_chronos()` - Request transformation
- `chronos_to_aleutian()` - Response transformation

**Coverage:**
- All supported model families (Chronos, TimesFM, Moirai, Granite, MOMENT)
- Case-insensitive model detection
- Error handling for unknown models
- Data preservation through transformations
- Edge cases (empty, very small, very large datasets)
- End-to-end transformation pipeline

### test_legacy_service.py
Tests service orchestration with mocked HTTP dependencies:
- `LegacyForecastService` initialization
- Model status checking and initialization
- Historical data fetching from data service
- Chronos inference execution
- Full forecast pipeline

**Coverage:**
- Service initialization
- Model already initialized (skip init)
- Model needs initialization
- Chronos-specific initialization payload
- Data service query endpoint usage
- Correct request/response formatting
- Error propagation
- Unsupported model handling

## Running Tests

### All Tests with Coverage
```bash
./run_tests.sh
```

### Quick Test (No Coverage)
```bash
./run_tests.sh --quick
```

### Specific Test File
```bash
pytest tests/core/test_legacy_schema.py -v
```

### Specific Test Class
```bash
pytest tests/core/test_legacy_adapters.py::TestDetermineModelFamily -v
```

### Specific Test Function
```bash
pytest tests/core/test_legacy_service.py::TestFullForecastPipeline::test_successful_forecast -v
```

### With Detailed Output
```bash
pytest tests/ -vv -s
```

### Failed Tests Only
```bash
pytest tests/ --lf  # last failed
pytest tests/ --ff  # failed first
```

## Coverage Reports

### Terminal Report
```bash
pytest tests/ --cov=forecast/core --cov-report=term-missing
```

### HTML Report
```bash
pytest tests/ --cov=forecast/core --cov-report=html
open htmlcov/index.html
```

### Coverage by File
```bash
pytest tests/ --cov=forecast/core --cov-report=term-missing:skip-covered
```

## Test Fixtures

Defined in `conftest.py`:

- `sample_aleutian_request` - Sample AleutianForecastRequest
- `sample_historical_prices` - Sample price data (90 days)
- `sample_chronos_response` - Sample ChronosInferenceResponse
- `mock_data_service_response` - Mock data service JSON response

**Usage:**
```python
def test_example(sample_aleutian_request):
    assert sample_aleutian_request.name == "SPY"
```

## Writing New Tests

### Template for Pure Function Tests
```python
def test_my_function():
    """Test description."""
    # Arrange
    input_data = {...}
    
    # Act
    result = my_function(input_data)
    
    # Assert
    assert result == expected_output
```

### Template for Async Service Tests
```python
@pytest.mark.asyncio
async def test_my_async_function():
    """Test description."""
    service = LegacyForecastService()
    
    # Mock HTTP responses
    mock_response = Mock()
    mock_response.json.return_value = {...}
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_context
        
        result = await service.some_method()
        
        assert result == expected
```

## Continuous Integration

### Pre-commit Hook
```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
./run_tests.sh --quick
```

### GitHub Actions
```yaml
- name: Run tests
  run: |
    pip install pytest pytest-asyncio pytest-cov
    pytest tests/ --cov=forecast/core --cov-fail-under=90
```

## Troubleshooting

### ImportError: No module named 'forecast'
```bash
# Ensure you're in the project root
cd /Users/jin/PycharmProjects/sapheneia

# Run tests from project root
pytest tests/
```

### AsyncIO Warnings
```bash
# Install pytest-asyncio
pip install pytest-asyncio

# Check pytest.ini has:
asyncio_mode = auto
```

### Coverage Not Generated
```bash
# Ensure pytest-cov is installed
pip install pytest-cov

# Check .coveragerc or pytest.ini configuration
```

## Best Practices

1. **One test, one assertion** (when possible)
2. **Use descriptive test names** - `test_chronos_models` not `test_models`
3. **Test edge cases** - empty, None, negative, very large
4. **Mock external dependencies** - HTTP calls, database, file I/O
5. **Use fixtures** - Reduce duplication
6. **Test error cases** - Not just happy path
7. **Keep tests fast** - Mock slow operations
8. **Maintain >90% coverage** - Run coverage checks regularly

## Test Coverage Goals

| Module | Target | Current |
|--------|--------|---------|
| legacy_schema.py | 95% | ✅ 95%+ |
| legacy_adapters.py | 95% | ✅ 95%+ |
| legacy_service.py | 90% | ✅ 90%+ |

## Shell Script Testing

The `scripts/` directory contains operational scripts for managing forecast models and running tests.

### Available Scripts

| Script | Purpose |
|--------|---------|
| `scripts/model-manager.sh` | Container lifecycle management (start/stop/init models) |
| `scripts/test-models.sh` | Systematic testing of all forecast models |
| `simulations/strategies/run_all_backtests.sh` | Run all backtest strategies with CSV export |
| `visualize.sh` | Terminal visualization of forecast results |

### model-manager.sh

Manages forecast model containers (podman/docker):

```bash
# List all models and their status
./scripts/model-manager.sh list

# Start a specific model container
./scripts/model-manager.sh start chronos-t5-tiny

# Start all models
./scripts/model-manager.sh start --all

# Initialize model after container starts
./scripts/model-manager.sh init chronos-t5-tiny

# Check running containers
./scripts/model-manager.sh status

# Stop a model
./scripts/model-manager.sh stop chronos-t5-tiny

# Build container image
./scripts/model-manager.sh build chronos-t5-tiny

# Pre-download HuggingFace model weights
./scripts/model-manager.sh pull chronos-t5-tiny
```

### test-models.sh

Systematic testing of forecast models at 4 levels:
1. Container starts (health check passes)
2. Model initializes (API returns ready)
3. Inference works (forecast returns valid data)
4. Backtest works (aleutian evaluate succeeds)

```bash
# Test all models
./scripts/test-models.sh

# Quick test (known-working models only)
./scripts/test-models.sh --quick

# Test specific model
./scripts/test-models.sh --model chronos-t5-tiny

# Test model family
./scripts/test-models.sh --family chronos

# Show last test report
./scripts/test-models.sh --report
```

### run_all_backtests.sh

Runs backtest strategies and exports results:

```bash
# Run all strategies (auto-fetches missing data)
./simulations/strategies/run_all_backtests.sh

# Run only SPY strategies
./simulations/strategies/run_all_backtests.sh --ticker SPY

# Run only chronos_tiny strategies
./simulations/strategies/run_all_backtests.sh --model tiny

# Dry run (show what would run)
./simulations/strategies/run_all_backtests.sh --dry-run

# Skip data fetching
./simulations/strategies/run_all_backtests.sh --skip-fetch
```

---

## Server Testing Guide

Step-by-step instructions for testing on the DIGITS server.

### Prerequisites

Ensure these services are running:
- InfluxDB (port 12130)
- Data service (port 12701)
- Forecast service (port 12700)
- At least one model container (e.g., chronos-t5-tiny on port 12710)

### Step 1: Check Service Status

```bash
# SSH to server
ssh digits

# Check running containers
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Or with docker
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected services:
| Service | Port | Health Check |
|---------|------|--------------|
| influxdb | 12130 | `curl http://localhost:12130/ping` |
| sapheneia-data | 12701 | `curl http://localhost:12701/health` |
| sapheneia-forecast | 12700 | `curl http://localhost:12700/health` |
| forecast-chronos-t5-tiny | 12710 | `curl http://localhost:12710/health` |

### Step 2: Verify Services Health

```bash
# Check InfluxDB
curl -s http://localhost:12130/ping && echo "InfluxDB OK"

# Check data service
curl -s http://localhost:12701/health | jq .

# Check forecast service
curl -s http://localhost:12700/health | jq .

# Check model container
curl -s http://localhost:12710/health | jq .
```

### Step 3: Initialize Model (if needed)

```bash
# Using model-manager
./scripts/model-manager.sh init chronos-t5-tiny

# Or manually via API
curl -X POST http://localhost:12710/init \
  -H "Content-Type: application/json" \
  -d '{"model_name": "amazon/chronos-t5-tiny"}'
```

### Step 4: Test Single Forecast

```bash
# Quick forecast test
curl -X POST http://localhost:12700/forecast \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${SAPHENEIA_API_KEY}" \
  -d '{
    "name": "SPY",
    "model": "amazon/chronos-t5-tiny",
    "context_size": 90,
    "horizon_size": 10
  }' | jq .
```

### Step 5: Run Model Tests

```bash
# Test specific model
./scripts/test-models.sh --model chronos-t5-tiny

# Quick test of working models
./scripts/test-models.sh --quick
```

### Step 6: Run Python Unit Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run orchestration tests
pytest orchestration/tests/ -v

# Run with coverage
pytest orchestration/tests/ --cov=orchestration --cov-report=term-missing
```

### Step 7: Run Full Backtest

```bash
# Single ticker backtest
./simulations/strategies/run_all_backtests.sh --ticker SPY --model tiny

# Or using aleutian CLI directly
aleutian evaluate \
  --config simulations/strategies/spy_chronos_tiny.yaml \
  --output results/
```

### Troubleshooting

#### Container won't start
```bash
# Check logs
podman logs forecast-chronos-t5-tiny

# Check if port is in use
ss -tlnp | grep 12710
```

#### Model initialization fails
```bash
# Check GPU availability
nvidia-smi

# Check model container logs
podman logs -f forecast-chronos-t5-tiny
```

#### Forecast returns empty
```bash
# Verify data exists in InfluxDB
curl -G 'http://localhost:12130/query' \
  --data-urlencode "db=sapheneia" \
  --data-urlencode "q=SELECT COUNT(*) FROM prices WHERE ticker='SPY'"
```

#### Connection refused
```bash
# Check if service is bound to correct interface
podman inspect forecast-chronos-t5-tiny | jq '.[0].NetworkSettings'

# Restart the service
./scripts/model-manager.sh stop chronos-t5-tiny
./scripts/model-manager.sh start chronos-t5-tiny
```

---

## Future Tests

- Integration tests with real containers
- Performance tests (latency, throughput)
- Stress tests (concurrent requests)
- End-to-end tests with AleutianLocal
- Property-based tests with Hypothesis
