# GAP-05: Add Python Unit Tests for Orchestration Module

**Priority:** CRITICAL
**Severity:** HIGH
**Category:** Testing
**Effort:** 2-3 days

---

## Architecture Review

### Reliability
- **Current Risk:** No test coverage means bugs go undetected
- **Mitigation:** Comprehensive unit + integration tests
- **Test Isolation:** Use mocks for external service calls
- **CI Integration:** Run tests on every commit

### Continuity
- **Regression Prevention:** Tests catch breaking changes
- **Documentation:** Tests serve as usage examples
- **Refactoring Safety:** Tests enable confident refactoring
- **Coverage Tracking:** Aim for 80%+ coverage on orchestration

### Integrity
- **Schema Validation:** Test all Pydantic models
- **Adapter Correctness:** Verify transformations preserve data
- **Edge Cases:** Test boundary conditions and error paths
- **Contract Testing:** Verify API contracts match documentation

### Optimization
- **Test Speed:** Use in-memory mocks, avoid network calls
- **Parallel Execution:** Tests should be independent
- **Fixture Reuse:** Share common fixtures across tests
- **Selective Running:** Support running subsets of tests

### Separation (Scalability)
- **Unit vs Integration:** Clear separation of test types
- **Module Isolation:** Each module has its own test file
- **Mock Boundaries:** Mock at service boundaries, not internals
- **Test Data:** Separate test data from production data

---

## Summary

The Python orchestration layer has **zero unit tests** while the Go data service has 21 tests. This is a critical gap that reduces confidence in the Python code and makes regressions likely to go undetected.

## Current State

```
Go Data Service:
████████████████████████████████████ 21 tests (GOOD)

Python Orchestration:
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0 tests (CRITICAL GAP)
```

Files needing tests (total ~1500 lines):
- `orchestration/schema.py` - 503 lines (Pydantic models)
- `orchestration/adapters.py` - 400 lines (Transformations)
- `orchestration/service.py` - 293 lines (Inference routing)
- `orchestration/router.py` - 346 lines (FastAPI endpoints)

## Acceptance Criteria

- [ ] Create `orchestration/tests/` directory structure
- [ ] `test_schema.py` - Pydantic model validation tests (20+ tests)
- [ ] `test_adapters.py` - Model transformation function tests (25+ tests)
- [ ] `test_service.py` - Inference routing tests with mocks (15+ tests)
- [ ] `test_router.py` - API endpoint tests (10+ tests)
- [ ] `conftest.py` - Shared fixtures
- [ ] Add to CI pipeline (GitHub Actions)
- [ ] Minimum 80% coverage on orchestration module
- [ ] All tests pass in < 30 seconds

## Implementation

### Directory Structure

```
orchestration/
├── __init__.py
├── adapters.py
├── router.py
├── schema.py
├── service.py
└── tests/
    ├── __init__.py
    ├── conftest.py           # Shared fixtures
    ├── test_schema.py        # Pydantic model tests
    ├── test_adapters.py      # Transformation tests
    ├── test_service.py       # Service tests with mocks
    └── test_router.py        # API endpoint tests
```

### File: `orchestration/tests/conftest.py`

```python
"""
Shared test fixtures for orchestration tests.
"""

import pytest
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import AsyncMock, Mock, patch

# Import schemas
from orchestration.schema import (
    InferenceRequest,
    InferenceResponse,
    ContextData,
    HorizonSpec,
    ForecastData,
    ContextSummary,
    InferenceMetadata,
    Period,
    DataSource,
    DataField,
    LegacyForecastRequest,
)


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_context_values() -> List[float]:
    """Sample price context data."""
    return [450.0, 451.2, 449.8, 452.1, 453.5, 451.0, 452.5, 450.8, 453.0, 454.2]


@pytest.fixture
def sample_forecast_values() -> List[float]:
    """Sample forecast values."""
    return [455.0, 456.2, 454.8, 457.1, 458.5]


@pytest.fixture
def sample_context_data(sample_context_values) -> ContextData:
    """Sample ContextData object."""
    return ContextData(
        values=sample_context_values,
        period=Period.DAY_1,
        source=DataSource.YAHOO,
        start_date="2025-09-01",
        end_date="2025-12-30",
        field=DataField.CLOSE,
    )


@pytest.fixture
def sample_horizon_spec() -> HorizonSpec:
    """Sample HorizonSpec object."""
    return HorizonSpec(
        length=10,
        period=Period.DAY_1,
    )


@pytest.fixture
def sample_inference_request(
    sample_context_data,
    sample_horizon_spec,
) -> InferenceRequest:
    """Sample complete InferenceRequest."""
    return InferenceRequest(
        request_id="test-request-001",
        ticker="SPY",
        model="amazon/chronos-t5-tiny",
        context=sample_context_data,
        horizon=sample_horizon_spec,
    )


@pytest.fixture
def sample_inference_response(sample_forecast_values) -> InferenceResponse:
    """Sample complete InferenceResponse."""
    return InferenceResponse(
        request_id="test-request-001",
        response_id="test-response-001",
        ticker="SPY",
        model="amazon/chronos-t5-tiny",
        forecast=ForecastData(
            values=sample_forecast_values,
            period=Period.DAY_1,
            start_date="2025-12-31",
            end_date="2026-01-06",
        ),
        context_summary=ContextSummary(
            length=10,
            period=Period.DAY_1,
            source=DataSource.YAHOO,
            start_date="2025-09-01",
            end_date="2025-12-30",
            field=DataField.CLOSE,
        ),
        metadata=InferenceMetadata(
            inference_time_ms=245,
            model_version="1.0.0",
            device="cpu",
            model_family="chronos",
        ),
    )


@pytest.fixture
def sample_legacy_request(sample_context_values) -> LegacyForecastRequest:
    """Sample legacy format request."""
    return LegacyForecastRequest(
        name="SPY",
        context_period_size=90,
        forecast_period_size=10,
        model="amazon/chronos-t5-tiny",
        recent_data=sample_context_values,
        as_of_date="2025-12-30",
    )


# =============================================================================
# MOCK FIXTURES
# =============================================================================

@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for testing HTTP calls."""
    with patch("httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = client_instance
        mock.return_value.__aexit__.return_value = None
        yield client_instance


@pytest.fixture
def mock_chronos_response() -> Dict[str, Any]:
    """Mock response from Chronos service."""
    return {
        "forecast": [455.0, 456.2, 454.8, 457.1, 458.5],
        "quantiles": {
            "0.1": [453.0, 454.0, 452.5, 455.0, 456.0],
            "0.9": [457.0, 458.5, 457.0, 459.5, 461.0],
        },
        "model_info": {
            "name": "chronos-t5-tiny",
            "version": "1.0.0",
        },
    }


@pytest.fixture
def mock_timesfm_response() -> Dict[str, Any]:
    """Mock response from TimesFM service."""
    return {
        "predictions": [[455.0, 456.2, 454.8, 457.1, 458.5]],
        "model_info": {
            "name": "timesfm-2.0",
            "version": "2.0.0",
        },
    }


# =============================================================================
# ASYNC TEST HELPERS
# =============================================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

### File: `orchestration/tests/test_schema.py`

```python
"""
Tests for orchestration/schema.py

Tests Pydantic models for validation, serialization, and edge cases.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from orchestration.schema import (
    Period,
    DataSource,
    DataField,
    ContextData,
    HorizonSpec,
    ModelParams,
    InferenceRequest,
    ForecastData,
    ContextSummary,
    InferenceMetadata,
    InferenceResponse,
    LegacyForecastRequest,
    LegacyForecastResponse,
)


class TestPeriodEnum:
    """Tests for Period enum."""

    def test_all_periods_defined(self):
        """All expected periods should be defined."""
        expected = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
        assert [p.value for p in Period] == expected

    def test_period_string_value(self):
        """Period should serialize to string value."""
        assert Period.DAY_1.value == "1d"
        assert Period.HOUR_1.value == "1h"


class TestDataSource:
    """Tests for DataSource enum."""

    def test_all_sources_defined(self):
        """All expected data sources should be defined."""
        sources = [s.value for s in DataSource]
        assert "yahoo" in sources
        assert "influxdb" in sources
        assert "synthetic" in sources


class TestContextData:
    """Tests for ContextData model."""

    def test_valid_context(self, sample_context_values):
        """Valid context data should be accepted."""
        ctx = ContextData(
            values=sample_context_values,
            period=Period.DAY_1,
            source=DataSource.YAHOO,
            start_date="2025-09-01",
            end_date="2025-12-30",
        )
        assert len(ctx.values) == 10
        assert ctx.period == Period.DAY_1

    def test_empty_values_rejected(self):
        """Empty values array should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ContextData(
                values=[],
                period=Period.DAY_1,
                source=DataSource.YAHOO,
                start_date="2025-09-01",
                end_date="2025-12-30",
            )
        assert "min_length" in str(exc_info.value)

    def test_invalid_date_format_rejected(self, sample_context_values):
        """Invalid date format should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ContextData(
                values=sample_context_values,
                period=Period.DAY_1,
                source=DataSource.YAHOO,
                start_date="2025/09/01",  # Wrong format
                end_date="2025-12-30",
            )
        assert "YYYY-MM-DD" in str(exc_info.value)

    def test_default_field_is_close(self, sample_context_values):
        """Default field should be CLOSE."""
        ctx = ContextData(
            values=sample_context_values,
            period=Period.DAY_1,
            source=DataSource.YAHOO,
            start_date="2025-09-01",
            end_date="2025-12-30",
        )
        assert ctx.field == DataField.CLOSE


class TestHorizonSpec:
    """Tests for HorizonSpec model."""

    def test_valid_horizon(self):
        """Valid horizon spec should be accepted."""
        horizon = HorizonSpec(length=10, period=Period.DAY_1)
        assert horizon.length == 10

    def test_zero_length_rejected(self):
        """Zero length should be rejected."""
        with pytest.raises(ValidationError):
            HorizonSpec(length=0, period=Period.DAY_1)

    def test_negative_length_rejected(self):
        """Negative length should be rejected."""
        with pytest.raises(ValidationError):
            HorizonSpec(length=-5, period=Period.DAY_1)

    def test_max_length_365(self):
        """Length above 365 should be rejected."""
        with pytest.raises(ValidationError):
            HorizonSpec(length=400, period=Period.DAY_1)


class TestModelParams:
    """Tests for ModelParams model."""

    def test_default_values(self):
        """Default values should be reasonable."""
        params = ModelParams()
        assert params.num_samples == 20
        assert params.temperature == 1.0
        assert params.top_k == 50
        assert params.top_p == 1.0

    def test_temperature_bounds(self):
        """Temperature should be bounded 0-2."""
        ModelParams(temperature=0.5)  # Valid
        ModelParams(temperature=2.0)  # Valid at boundary

        with pytest.raises(ValidationError):
            ModelParams(temperature=0)  # Too low

        with pytest.raises(ValidationError):
            ModelParams(temperature=2.5)  # Too high


class TestInferenceRequest:
    """Tests for InferenceRequest model."""

    def test_auto_generated_request_id(self, sample_context_data, sample_horizon_spec):
        """Request ID should be auto-generated if not provided."""
        req = InferenceRequest(
            ticker="SPY",
            model="amazon/chronos-t5-tiny",
            context=sample_context_data,
            horizon=sample_horizon_spec,
        )
        assert req.request_id is not None
        assert len(req.request_id) == 36  # UUID format

    def test_auto_generated_timestamp(self, sample_context_data, sample_horizon_spec):
        """Timestamp should be auto-generated."""
        req = InferenceRequest(
            ticker="SPY",
            model="amazon/chronos-t5-tiny",
            context=sample_context_data,
            horizon=sample_horizon_spec,
        )
        assert req.timestamp is not None
        assert req.timestamp.tzinfo == timezone.utc

    def test_ticker_length_validation(self, sample_context_data, sample_horizon_spec):
        """Ticker should have length limits."""
        # Too long
        with pytest.raises(ValidationError):
            InferenceRequest(
                ticker="A" * 25,
                model="amazon/chronos-t5-tiny",
                context=sample_context_data,
                horizon=sample_horizon_spec,
            )

    def test_json_serialization(self, sample_inference_request):
        """Request should serialize to JSON correctly."""
        json_str = sample_inference_request.model_dump_json()
        assert "SPY" in json_str
        assert "chronos-t5-tiny" in json_str


class TestInferenceResponse:
    """Tests for InferenceResponse model."""

    def test_response_links_to_request(self, sample_inference_response):
        """Response should reference request ID."""
        assert sample_inference_response.request_id == "test-request-001"
        assert sample_inference_response.response_id == "test-response-001"

    def test_forecast_data_present(self, sample_inference_response):
        """Forecast data should be present."""
        assert len(sample_inference_response.forecast.values) == 5
        assert sample_inference_response.forecast.period == Period.DAY_1


class TestLegacyFormats:
    """Tests for legacy request/response formats."""

    def test_legacy_request_valid(self, sample_context_values):
        """Legacy request should validate."""
        req = LegacyForecastRequest(
            name="SPY",
            context_period_size=90,
            forecast_period_size=10,
            model="amazon/chronos-t5-tiny",
            recent_data=sample_context_values,
        )
        assert req.name == "SPY"

    def test_legacy_response_valid(self, sample_forecast_values):
        """Legacy response should validate."""
        resp = LegacyForecastResponse(
            name="SPY",
            forecast=sample_forecast_values,
        )
        assert resp.message == "Success"
```

### File: `orchestration/tests/test_adapters.py`

```python
"""
Tests for orchestration/adapters.py

Tests model transformation functions.
"""

import pytest
from orchestration.adapters import (
    determine_model_family,
    get_model_endpoint,
    inference_to_chronos,
    chronos_to_inference,
    inference_to_timesfm,
    timesfm_to_inference,
    legacy_to_inference,
    inference_to_legacy,
    calculate_forecast_dates,
)
from orchestration.schema import (
    InferenceRequest,
    InferenceResponse,
    Period,
    DataSource,
)


class TestDetermineModelFamily:
    """Tests for determine_model_family function."""

    @pytest.mark.parametrize("model_name,expected_family", [
        ("amazon/chronos-t5-tiny", "chronos"),
        ("amazon/chronos-t5-base", "chronos"),
        ("amazon/chronos-bolt-mini", "chronos"),
        ("google/timesfm-2.0", "timesfm"),
        ("google/timesfm", "timesfm"),
        ("salesforce/moirai-1.0-R-small", "moirai"),
        ("ibm/granite-timeseries", "granite"),
        ("autolab/moment-base", "moment"),
        ("huggingface/lag-llama", "lagllama"),
        ("alibaba/yinglong-300M", "yinglong"),
    ])
    def test_known_model_families(self, model_name, expected_family):
        """Known models should return correct family."""
        assert determine_model_family(model_name) == expected_family

    def test_case_insensitive(self):
        """Model name matching should be case-insensitive."""
        assert determine_model_family("AMAZON/CHRONOS-T5-TINY") == "chronos"
        assert determine_model_family("Google/TimesFM-2.0") == "timesfm"

    def test_unknown_model_raises(self):
        """Unknown model should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            determine_model_family("unknown/model-name")
        assert "Unknown model family" in str(exc_info.value)


class TestGetModelEndpoint:
    """Tests for get_model_endpoint function."""

    def test_chronos_endpoint(self):
        """Chronos should return correct endpoint."""
        endpoint = get_model_endpoint("chronos")
        assert "inference" in endpoint.lower()

    def test_timesfm_endpoint(self):
        """TimesFM should return correct endpoint."""
        endpoint = get_model_endpoint("timesfm")
        assert "timesfm" in endpoint.lower() or "inference" in endpoint.lower()


class TestInferenceToChronos:
    """Tests for inference_to_chronos transformation."""

    def test_basic_transformation(self, sample_inference_request):
        """Request should transform to Chronos format."""
        result = inference_to_chronos(sample_inference_request)

        assert "context" in result
        assert result["context"] == sample_inference_request.context.values
        assert "prediction_length" in result
        assert result["prediction_length"] == sample_inference_request.horizon.length

    def test_model_params_included(self, sample_inference_request):
        """Model params should be included if present."""
        from orchestration.schema import ModelParams

        sample_inference_request.params = ModelParams(
            num_samples=50,
            temperature=0.8,
        )
        result = inference_to_chronos(sample_inference_request)

        assert result.get("num_samples") == 50
        assert result.get("temperature") == 0.8


class TestChronosToInference:
    """Tests for chronos_to_inference transformation."""

    def test_basic_transformation(
        self,
        mock_chronos_response,
        sample_inference_request,
    ):
        """Chronos response should transform to unified format."""
        result = chronos_to_inference(
            mock_chronos_response,
            sample_inference_request,
            inference_time_ms=245,
        )

        assert isinstance(result, InferenceResponse)
        assert result.request_id == sample_inference_request.request_id
        assert len(result.forecast.values) == 5
        assert result.metadata.inference_time_ms == 245
        assert result.metadata.model_family == "chronos"

    def test_quantiles_extracted(
        self,
        mock_chronos_response,
        sample_inference_request,
    ):
        """Quantiles should be extracted if present."""
        result = chronos_to_inference(
            mock_chronos_response,
            sample_inference_request,
            inference_time_ms=245,
        )

        if result.quantiles:
            assert len(result.quantiles) >= 2


class TestInferenceToTimesFM:
    """Tests for inference_to_timesfm transformation."""

    def test_batch_format(self, sample_inference_request):
        """TimesFM requires batch format (list of lists)."""
        result = inference_to_timesfm(sample_inference_request)

        assert "target_inputs" in result
        assert isinstance(result["target_inputs"], list)
        # Should be list of lists for batch inference
        assert isinstance(result["target_inputs"][0], list)


class TestTimesFMToInference:
    """Tests for timesfm_to_inference transformation."""

    def test_extracts_first_series(
        self,
        mock_timesfm_response,
        sample_inference_request,
    ):
        """Should extract first series from batch response."""
        result = timesfm_to_inference(
            mock_timesfm_response,
            sample_inference_request,
            inference_time_ms=300,
        )

        assert isinstance(result, InferenceResponse)
        assert len(result.forecast.values) == 5


class TestLegacyAdapters:
    """Tests for legacy format adapters."""

    def test_legacy_to_inference(self, sample_legacy_request):
        """Legacy request should convert to new format."""
        result = legacy_to_inference(
            sample_legacy_request,
            source=DataSource.INFLUXDB,
            period=Period.DAY_1,
        )

        assert isinstance(result, InferenceRequest)
        assert result.ticker == sample_legacy_request.name
        assert result.model == sample_legacy_request.model
        assert len(result.context.values) == len(sample_legacy_request.recent_data)

    def test_inference_to_legacy(self, sample_inference_response):
        """Unified response should convert to legacy format."""
        from orchestration.schema import LegacyForecastResponse

        result = inference_to_legacy(sample_inference_response)

        assert isinstance(result, LegacyForecastResponse)
        assert result.name == sample_inference_response.ticker
        assert len(result.forecast) == len(sample_inference_response.forecast.values)


class TestCalculateForecastDates:
    """Tests for calculate_forecast_dates function."""

    def test_daily_dates(self):
        """Daily forecast dates should increment by 1 day."""
        start, end = calculate_forecast_dates(
            context_end_date="2025-12-30",
            horizon_length=5,
            period=Period.DAY_1,
        )

        assert start == "2025-12-31"
        assert end == "2026-01-04"

    def test_weekly_dates(self):
        """Weekly forecast dates should increment by 7 days."""
        start, end = calculate_forecast_dates(
            context_end_date="2025-12-30",
            horizon_length=4,
            period=Period.WEEK_1,
        )

        # Should be 4 weeks later
        assert "2026-01" in end
```

### File: `orchestration/tests/test_service.py`

```python
"""
Tests for orchestration/service.py

Tests inference service with mocked HTTP calls.
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
import httpx

from orchestration.service import InferenceService, LegacyCompatService
from orchestration.schema import InferenceResponse, LegacyForecastResponse


class TestInferenceService:
    """Tests for InferenceService class."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return InferenceService(
            base_url="http://test:8000",
            api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_predict_routes_to_chronos(
        self,
        service,
        sample_inference_request,
        mock_httpx_client,
        mock_chronos_response,
    ):
        """Chronos models should route to Chronos handler."""
        # Setup mock
        mock_response = Mock()
        mock_response.json.return_value = mock_chronos_response
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        # Call service
        result = await service.predict(sample_inference_request)

        # Verify
        assert isinstance(result, InferenceResponse)
        assert result.request_id == sample_inference_request.request_id
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_predict_routes_to_timesfm(
        self,
        service,
        sample_inference_request,
        mock_timesfm_response,
    ):
        """TimesFM models should route to TimesFM handler."""
        sample_inference_request.model = "google/timesfm-2.0"

        with patch.object(
            service,
            "_run_timesfm_inference",
            new_callable=AsyncMock,
        ) as mock_timesfm:
            mock_timesfm.return_value = Mock(spec=InferenceResponse)

            await service.predict(sample_inference_request)

            mock_timesfm.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_error_raised(
        self,
        service,
        sample_inference_request,
        mock_httpx_client,
    ):
        """HTTP errors should propagate."""
        mock_httpx_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=Mock(status_code=500),
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await service._run_chronos_inference(sample_inference_request)

    @pytest.mark.asyncio
    async def test_timeout_configuration(self, service):
        """Service should use configured timeout."""
        assert service.timeout == 300.0


class TestLegacyCompatService:
    """Tests for LegacyCompatService class."""

    @pytest.fixture
    def legacy_service(self):
        """Create legacy compat service."""
        inference_service = InferenceService()
        return LegacyCompatService(inference_service)

    @pytest.mark.asyncio
    async def test_legacy_forecast_converts_format(
        self,
        legacy_service,
        sample_legacy_request,
        sample_inference_response,
    ):
        """Legacy forecast should convert formats correctly."""
        with patch.object(
            legacy_service.inference_service,
            "predict",
            new_callable=AsyncMock,
        ) as mock_predict:
            mock_predict.return_value = sample_inference_response

            result = await legacy_service.forecast(sample_legacy_request)

            assert isinstance(result, LegacyForecastResponse)
            assert result.name == sample_legacy_request.name
            mock_predict.assert_called_once()
```

### Update `pyproject.toml`

```toml
[tool.pytest.ini_options]
testpaths = ["orchestration/tests", "tests"]
asyncio_mode = "auto"
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["orchestration"]
omit = ["orchestration/tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
fail_under = 80
```

## Running Tests

```bash
# Run all orchestration tests
pytest orchestration/tests/ -v

# Run with coverage
pytest orchestration/tests/ --cov=orchestration --cov-report=html

# Run specific test file
pytest orchestration/tests/test_schema.py -v

# Run specific test class
pytest orchestration/tests/test_adapters.py::TestDetermineModelFamily -v
```

## CI Integration

Add to `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [main, aleutian_merge]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: |
          pytest orchestration/tests/ --cov=orchestration --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

## Dependencies

- None (foundational work)

## Related Files

- `orchestration/schema.py`
- `orchestration/adapters.py`
- `orchestration/service.py`
- `orchestration/router.py`
- `pyproject.toml`
- New: `orchestration/tests/*.py`
