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

## Future Tests

- Integration tests with real containers
- Performance tests (latency, throughput)
- Stress tests (concurrent requests)
- End-to-end tests with AleutianLocal
- Property-based tests with Hypothesis
