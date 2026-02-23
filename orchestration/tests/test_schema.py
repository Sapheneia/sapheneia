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
    QuantileForecast,
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
        assert Period.MINUTE_1.value == "1m"
        assert Period.WEEK_1.value == "1w"


class TestDataSource:
    """Tests for DataSource enum."""

    def test_all_sources_defined(self):
        """All expected data sources should be defined."""
        sources = [s.value for s in DataSource]
        assert "yahoo" in sources
        assert "influxdb" in sources
        assert "synthetic" in sources
        assert "alpaca" in sources
        assert "binance" in sources

    def test_source_string_value(self):
        """DataSource should serialize to string value."""
        assert DataSource.YAHOO.value == "yahoo"
        assert DataSource.INFLUXDB.value == "influxdb"


class TestDataField:
    """Tests for DataField enum."""

    def test_ohlcv_fields_defined(self):
        """All OHLCV fields should be defined."""
        fields = [f.value for f in DataField]
        assert "open" in fields
        assert "high" in fields
        assert "low" in fields
        assert "close" in fields
        assert "volume" in fields


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
        assert ctx.source == DataSource.YAHOO

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
        assert "min_length" in str(exc_info.value).lower() or "at least 1" in str(exc_info.value).lower()

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

    def test_custom_field(self, sample_context_values):
        """Custom field should be accepted."""
        ctx = ContextData(
            values=sample_context_values,
            period=Period.DAY_1,
            source=DataSource.YAHOO,
            start_date="2025-09-01",
            end_date="2025-12-30",
            field=DataField.VOLUME,
        )
        assert ctx.field == DataField.VOLUME

    def test_single_value_allowed(self):
        """Single value should be allowed (min_length=1)."""
        ctx = ContextData(
            values=[100.0],
            period=Period.DAY_1,
            source=DataSource.YAHOO,
            start_date="2025-12-30",
            end_date="2025-12-30",
        )
        assert len(ctx.values) == 1


class TestHorizonSpec:
    """Tests for HorizonSpec model."""

    def test_valid_horizon(self):
        """Valid horizon spec should be accepted."""
        horizon = HorizonSpec(length=10, period=Period.DAY_1)
        assert horizon.length == 10
        assert horizon.period == Period.DAY_1

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

    def test_boundary_length_365(self):
        """Length of exactly 365 should be accepted."""
        horizon = HorizonSpec(length=365, period=Period.DAY_1)
        assert horizon.length == 365


class TestModelParams:
    """Tests for ModelParams model."""

    def test_default_values(self):
        """Default values should be reasonable."""
        params = ModelParams()
        assert params.num_samples == 20
        assert params.temperature == 1.0
        assert params.top_k == 50
        assert params.top_p == 1.0
        assert params.quantiles is None

    def test_custom_num_samples(self):
        """Custom num_samples should be accepted."""
        params = ModelParams(num_samples=50)
        assert params.num_samples == 50

    def test_num_samples_max_100(self):
        """num_samples above 100 should be rejected."""
        with pytest.raises(ValidationError):
            ModelParams(num_samples=150)

    def test_temperature_bounds(self):
        """Temperature should be bounded (0, 2]."""
        ModelParams(temperature=0.5)  # Valid
        ModelParams(temperature=2.0)  # Valid at boundary

        with pytest.raises(ValidationError):
            ModelParams(temperature=0)  # Too low (must be > 0)

        with pytest.raises(ValidationError):
            ModelParams(temperature=2.5)  # Too high

    def test_quantiles_list(self):
        """Quantiles should accept list of floats."""
        params = ModelParams(quantiles=[0.1, 0.5, 0.9])
        assert params.quantiles == [0.1, 0.5, 0.9]


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

    def test_custom_request_id(self, sample_context_data, sample_horizon_spec):
        """Custom request ID should be used if provided."""
        req = InferenceRequest(
            request_id="my-custom-id",
            ticker="SPY",
            model="amazon/chronos-t5-tiny",
            context=sample_context_data,
            horizon=sample_horizon_spec,
        )
        assert req.request_id == "my-custom-id"

    def test_ticker_length_validation_max(self, sample_context_data, sample_horizon_spec):
        """Ticker should have max length of 20."""
        with pytest.raises(ValidationError):
            InferenceRequest(
                ticker="A" * 25,
                model="amazon/chronos-t5-tiny",
                context=sample_context_data,
                horizon=sample_horizon_spec,
            )

    def test_ticker_length_validation_min(self, sample_context_data, sample_horizon_spec):
        """Ticker should have min length of 1."""
        with pytest.raises(ValidationError):
            InferenceRequest(
                ticker="",
                model="amazon/chronos-t5-tiny",
                context=sample_context_data,
                horizon=sample_horizon_spec,
            )

    def test_json_serialization(self, sample_inference_request):
        """Request should serialize to JSON correctly."""
        json_str = sample_inference_request.model_dump_json()
        assert "SPY" in json_str
        assert "chronos-t5-tiny" in json_str
        assert "test-request-001" in json_str

    def test_optional_params(self, sample_context_data, sample_horizon_spec):
        """Params should be optional."""
        req = InferenceRequest(
            ticker="SPY",
            model="amazon/chronos-t5-tiny",
            context=sample_context_data,
            horizon=sample_horizon_spec,
        )
        assert req.params is None


class TestForecastData:
    """Tests for ForecastData model."""

    def test_valid_forecast(self, sample_forecast_values):
        """Valid forecast data should be accepted."""
        forecast = ForecastData(
            values=sample_forecast_values,
            period=Period.DAY_1,
            start_date="2025-12-31",
            end_date="2026-01-04",
        )
        assert len(forecast.values) == 5
        assert forecast.period == Period.DAY_1

    def test_empty_values_rejected(self):
        """Empty values should be rejected."""
        with pytest.raises(ValidationError):
            ForecastData(
                values=[],
                period=Period.DAY_1,
                start_date="2025-12-31",
                end_date="2026-01-04",
            )


class TestContextSummary:
    """Tests for ContextSummary model."""

    def test_valid_summary(self):
        """Valid context summary should be accepted."""
        summary = ContextSummary(
            length=90,
            period=Period.DAY_1,
            source=DataSource.YAHOO,
            start_date="2025-09-01",
            end_date="2025-12-30",
            field=DataField.CLOSE,
        )
        assert summary.length == 90
        assert summary.field == DataField.CLOSE


class TestInferenceMetadata:
    """Tests for InferenceMetadata model."""

    def test_required_inference_time(self):
        """inference_time_ms should be required."""
        metadata = InferenceMetadata(inference_time_ms=245)
        assert metadata.inference_time_ms == 245

    def test_optional_fields(self):
        """Optional fields should default to None."""
        metadata = InferenceMetadata(inference_time_ms=245)
        assert metadata.model_version is None
        assert metadata.device is None
        assert metadata.model_family is None

    def test_all_fields(self):
        """All fields should be settable."""
        metadata = InferenceMetadata(
            inference_time_ms=245,
            model_version="1.0.0",
            device="cuda:0",
            model_family="chronos",
        )
        assert metadata.model_version == "1.0.0"
        assert metadata.device == "cuda:0"
        assert metadata.model_family == "chronos"


class TestQuantileForecast:
    """Tests for QuantileForecast model."""

    def test_valid_quantile(self, sample_forecast_values):
        """Valid quantile forecast should be accepted."""
        qf = QuantileForecast(
            quantile=0.1,
            values=sample_forecast_values,
        )
        assert qf.quantile == 0.1
        assert len(qf.values) == 5


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

    def test_auto_generated_response_id(self, sample_forecast_values):
        """Response ID should be auto-generated if not provided."""
        response = InferenceResponse(
            request_id="test-request",
            ticker="SPY",
            model="amazon/chronos-t5-tiny",
            forecast=ForecastData(
                values=sample_forecast_values,
                period=Period.DAY_1,
                start_date="2025-12-31",
                end_date="2026-01-04",
            ),
            context_summary=ContextSummary(
                length=10,
                period=Period.DAY_1,
                source=DataSource.YAHOO,
                start_date="2025-09-01",
                end_date="2025-12-30",
                field=DataField.CLOSE,
            ),
            metadata=InferenceMetadata(inference_time_ms=100),
        )
        assert response.response_id is not None
        assert len(response.response_id) == 36

    def test_json_serialization(self, sample_inference_response):
        """Response should serialize to JSON correctly."""
        json_str = sample_inference_response.model_dump_json()
        assert "test-request-001" in json_str
        assert "SPY" in json_str


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
        assert req.context_period_size == 90
        assert req.forecast_period_size == 10
        assert req.as_of_date is None

    def test_legacy_request_with_date(self, sample_context_values):
        """Legacy request with as_of_date should validate."""
        req = LegacyForecastRequest(
            name="SPY",
            context_period_size=90,
            forecast_period_size=10,
            model="amazon/chronos-t5-tiny",
            recent_data=sample_context_values,
            as_of_date="2025-12-30",
        )
        assert req.as_of_date == "2025-12-30"

    def test_legacy_response_valid(self, sample_forecast_values):
        """Legacy response should validate."""
        resp = LegacyForecastResponse(
            name="SPY",
            forecast=sample_forecast_values,
        )
        assert resp.message == "Success"
        assert len(resp.forecast) == 5

    def test_legacy_response_custom_message(self, sample_forecast_values):
        """Legacy response should accept custom message."""
        resp = LegacyForecastResponse(
            name="SPY",
            forecast=sample_forecast_values,
            message="Custom message",
        )
        assert resp.message == "Custom message"

    def test_legacy_request_empty_data_rejected(self):
        """Legacy request with empty data should be rejected."""
        with pytest.raises(ValidationError):
            LegacyForecastRequest(
                name="SPY",
                context_period_size=90,
                forecast_period_size=10,
                model="amazon/chronos-t5-tiny",
                recent_data=[],
            )

    def test_legacy_request_zero_forecast_rejected(self, sample_context_values):
        """Legacy request with zero forecast size should be rejected."""
        with pytest.raises(ValidationError):
            LegacyForecastRequest(
                name="SPY",
                context_period_size=90,
                forecast_period_size=0,
                model="amazon/chronos-t5-tiny",
                recent_data=sample_context_values,
            )
