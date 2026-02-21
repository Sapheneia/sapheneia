"""
Tests for orchestration/adapters.py

Tests model transformation functions.
"""

import pytest
from datetime import date

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
    parse_date,
    DateParseError,
)
from orchestration.schema import (
    InferenceRequest,
    InferenceResponse,
    Period,
    DataSource,
    DataField,
    LegacyForecastResponse,
    ModelParams,
)
from shared.errors import ComputationError


class TestDetermineModelFamily:
    """Tests for determine_model_family function."""

    @pytest.mark.parametrize("model_name,expected_family", [
        ("amazon/chronos-t5-tiny", "chronos"),
        ("amazon/chronos-t5-base", "chronos"),
        ("amazon/chronos-t5-large", "chronos"),
        ("amazon/chronos-bolt-mini", "chronos"),
        ("amazon/chronos-bolt-small", "chronos"),
        ("google/timesfm-2.0", "timesfm"),
        ("google/timesfm-1.0", "timesfm"),
        ("google/timesfm-2.0-500m-pytorch", "timesfm"),
        ("salesforce/moirai-1.0-R-small", "moirai"),
        ("salesforce/moirai-1.1-R-large", "moirai"),
        ("ibm/granite-timeseries-ttm", "granite"),
        ("ibm/granite-ttm-512", "granite"),
        ("autolab/moment-base", "moment"),
        ("AutonLab/moment-1-large", "moment"),
        ("huggingface/lag-llama", "lagllama"),
        ("time-series-foundation-models/lag-llama", "lagllama"),
        ("alibaba/yinglong-300M", "yinglong"),
    ])
    def test_known_model_families(self, model_name, expected_family):
        """Known models should return correct family."""
        assert determine_model_family(model_name) == expected_family

    def test_case_insensitive(self):
        """Model name matching should be case-insensitive."""
        assert determine_model_family("AMAZON/CHRONOS-T5-TINY") == "chronos"
        assert determine_model_family("Google/TimesFM-2.0") == "timesfm"
        assert determine_model_family("IBM/Granite-TTM") == "granite"

    def test_unknown_model_raises(self):
        """Unknown model should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            determine_model_family("unknown/model-name")
        assert "Unknown model family" in str(exc_info.value)

    def test_partial_match_not_allowed(self):
        """Partial model names that don't match patterns should raise."""
        with pytest.raises(ValueError):
            determine_model_family("amazon/other-model")


class TestGetModelEndpoint:
    """Tests for get_model_endpoint function."""

    def test_chronos_endpoint(self):
        """Chronos should return correct endpoint."""
        endpoint = get_model_endpoint("chronos")
        assert endpoint == "/forecast/v1/chronos/inference"

    def test_timesfm_endpoint(self):
        """TimesFM should return correct endpoint."""
        endpoint = get_model_endpoint("timesfm")
        assert endpoint == "/forecast/v1/timesfm20/inference"

    def test_moirai_endpoint(self):
        """Moirai should return correct endpoint."""
        endpoint = get_model_endpoint("moirai")
        assert endpoint == "/forecast/v1/moirai/inference"

    def test_granite_endpoint(self):
        """Granite should return correct endpoint."""
        endpoint = get_model_endpoint("granite")
        assert endpoint == "/forecast/v1/granite/inference"

    def test_moment_endpoint(self):
        """Moment should return correct endpoint."""
        endpoint = get_model_endpoint("moment")
        assert endpoint == "/forecast/v1/moment/inference"

    def test_unknown_family_raises(self):
        """Unknown model family should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_model_endpoint("unknown_family")
        assert "No endpoint for model family" in str(exc_info.value)


class TestParseDate:
    """Tests for parse_date function."""

    def test_parse_yyyy_mm_dd_format(self):
        """Should parse YYYY-MM-DD format."""
        result = parse_date("2025-12-30", "test_date")
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 30

    def test_parse_yyyymmdd_format(self):
        """Should parse YYYYMMDD format."""
        result = parse_date("20251230", "test_date")
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 30

    def test_parse_iso_format_with_time(self):
        """Should parse ISO format with time component."""
        result = parse_date("2025-12-30T14:30:00", "test_date")
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 30

    def test_parse_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        result = parse_date("  2025-12-30  ", "test_date")
        assert result.year == 2025

    def test_empty_date_raises_error(self):
        """Empty date string should raise DateParseError."""
        with pytest.raises(DateParseError) as exc_info:
            parse_date("", "my_field")
        assert "my_field is required but was empty" in str(exc_info.value)

    def test_none_date_raises_error(self):
        """None date should raise DateParseError."""
        with pytest.raises(DateParseError):
            parse_date(None, "test_field")

    def test_invalid_format_raises_error(self):
        """Invalid format should raise DateParseError."""
        with pytest.raises(DateParseError) as exc_info:
            parse_date("12/30/2025", "date_field")
        assert "Invalid date_field format" in str(exc_info.value)
        assert "12/30/2025" in str(exc_info.value)

    def test_invalid_date_values_raise_error(self):
        """Invalid date values (e.g., month 13) should raise DateParseError."""
        with pytest.raises(DateParseError):
            parse_date("2025-13-30", "test_date")

    def test_error_includes_field_name(self):
        """Error message should include the field name."""
        with pytest.raises(DateParseError) as exc_info:
            parse_date("bad-date", "my_special_field")
        assert "my_special_field" in str(exc_info.value)

    def test_partial_yyyymmdd_raises_error(self):
        """Partial YYYYMMDD format should raise error."""
        with pytest.raises(DateParseError):
            parse_date("2025123", "test_date")  # Missing one digit


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
        assert start == "2026-01-06"  # 1 week after
        assert end == "2026-01-27"  # 4 weeks after

    def test_hourly_dates(self):
        """Hourly forecast dates should work (stored as date string)."""
        start, end = calculate_forecast_dates(
            context_end_date="2025-12-30",
            horizon_length=24,
            period=Period.HOUR_1,
        )
        # Hourly increments from midnight
        assert start == "2025-12-30"  # Same day (1 hour after midnight)
        assert end == "2025-12-31"  # 24 hours later

    def test_monthly_dates(self):
        """Monthly forecast dates should use 30-day approximation."""
        start, end = calculate_forecast_dates(
            context_end_date="2025-12-01",
            horizon_length=3,
            period=Period.MONTH_1,
        )
        # 30-day approximation
        assert "2026" in end or "2025-12" in end

    def test_single_period(self):
        """Single period horizon should work."""
        start, end = calculate_forecast_dates(
            context_end_date="2025-12-30",
            horizon_length=1,
            period=Period.DAY_1,
        )
        assert start == "2025-12-31"
        assert end == "2025-12-31"

    def test_yyyymmdd_format(self):
        """Should accept YYYYMMDD format."""
        start, end = calculate_forecast_dates(
            context_end_date="20251230",
            horizon_length=5,
            period=Period.DAY_1,
        )
        assert start == "2025-12-31"
        assert end == "2026-01-04"

    def test_invalid_date_raises_error(self):
        """Invalid date format should raise DateParseError."""
        with pytest.raises(DateParseError) as exc_info:
            calculate_forecast_dates(
                context_end_date="12/30/2025",  # Invalid format
                horizon_length=5,
                period=Period.DAY_1,
            )
        assert "context_end_date" in str(exc_info.value)

    def test_empty_date_raises_error(self):
        """Empty date should raise DateParseError."""
        with pytest.raises(DateParseError):
            calculate_forecast_dates(
                context_end_date="",
                horizon_length=5,
                period=Period.DAY_1,
            )


class TestInferenceToChronos:
    """Tests for inference_to_chronos transformation."""

    def test_basic_transformation(self, sample_inference_request):
        """Request should transform to Chronos format."""
        result = inference_to_chronos(sample_inference_request)

        assert "context" in result
        assert result["context"] == sample_inference_request.context.values
        assert "prediction_length" in result
        assert result["prediction_length"] == sample_inference_request.horizon.length

    def test_default_params(self, sample_inference_request):
        """Default params should be included."""
        result = inference_to_chronos(sample_inference_request)

        assert result["num_samples"] == 20
        assert result["temperature"] == 1.0
        assert result["top_k"] == 50
        assert result["top_p"] == 1.0

    def test_custom_params(self, sample_inference_request):
        """Custom params should override defaults."""
        sample_inference_request.params = ModelParams(
            num_samples=50,
            temperature=0.8,
            top_k=100,
            top_p=0.95,
        )
        result = inference_to_chronos(sample_inference_request)

        assert result["num_samples"] == 50
        assert result["temperature"] == 0.8
        assert result["top_k"] == 100
        assert result["top_p"] == 0.95

    def test_context_values_preserved(self, sample_inference_request):
        """Context values should be passed through exactly."""
        original_values = sample_inference_request.context.values.copy()
        result = inference_to_chronos(sample_inference_request)

        assert result["context"] == original_values


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

    def test_context_summary_preserved(
        self,
        mock_chronos_response,
        sample_inference_request,
    ):
        """Context summary should reflect original request."""
        result = chronos_to_inference(
            mock_chronos_response,
            sample_inference_request,
            inference_time_ms=245,
        )

        assert result.context_summary.length == len(sample_inference_request.context.values)
        assert result.context_summary.period == sample_inference_request.context.period
        assert result.context_summary.source == sample_inference_request.context.source

    def test_forecast_dates_calculated(
        self,
        mock_chronos_response,
        sample_inference_request,
    ):
        """Forecast dates should be calculated from context end."""
        result = chronos_to_inference(
            mock_chronos_response,
            sample_inference_request,
            inference_time_ms=245,
        )

        # Forecast should start after context ends
        assert result.forecast.start_date > sample_inference_request.context.end_date

    def test_quantiles_extracted_when_present(
        self,
        mock_chronos_response,
        sample_inference_request,
    ):
        """Quantiles should be extracted if present in response."""
        result = chronos_to_inference(
            mock_chronos_response,
            sample_inference_request,
            inference_time_ms=245,
        )

        if result.quantiles:
            assert len(result.quantiles) >= 2
            assert any(q.quantile == 0.1 for q in result.quantiles)
            assert any(q.quantile == 0.9 for q in result.quantiles)

    def test_response_without_quantiles(self, sample_inference_request):
        """Response without quantiles should still work."""
        chronos_response = {
            "prediction": {
                "median": [455.0, 456.2, 454.8],
            }
        }
        result = chronos_to_inference(
            chronos_response,
            sample_inference_request,
            inference_time_ms=100,
        )

        assert isinstance(result, InferenceResponse)
        assert result.quantiles is None or len(result.quantiles) == 0


class TestInferenceToTimesFM:
    """Tests for inference_to_timesfm transformation."""

    def test_batch_format(self, sample_inference_request):
        """TimesFM requires batch format (list of lists)."""
        result = inference_to_timesfm(sample_inference_request)

        assert "target_inputs" in result
        assert isinstance(result["target_inputs"], list)
        assert isinstance(result["target_inputs"][0], list)
        assert result["target_inputs"][0] == sample_inference_request.context.values

    def test_parameters_included(self, sample_inference_request):
        """Parameters should include context and horizon lengths."""
        result = inference_to_timesfm(sample_inference_request)

        assert "parameters" in result
        params = result["parameters"]
        assert params["context_len"] == len(sample_inference_request.context.values)
        assert params["horizon_len"] == sample_inference_request.horizon.length

    def test_covariates_null(self, sample_inference_request):
        """Covariates should be None by default."""
        result = inference_to_timesfm(sample_inference_request)
        assert result["covariates"] is None


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

    def test_model_family_is_timesfm(
        self,
        mock_timesfm_response,
        sample_inference_request,
    ):
        """Model family should be timesfm."""
        result = timesfm_to_inference(
            mock_timesfm_response,
            sample_inference_request,
            inference_time_ms=300,
        )

        assert result.metadata.model_family == "timesfm"

    def test_inference_time_preserved(
        self,
        mock_timesfm_response,
        sample_inference_request,
    ):
        """Inference time should be preserved."""
        result = timesfm_to_inference(
            mock_timesfm_response,
            sample_inference_request,
            inference_time_ms=500,
        )

        assert result.metadata.inference_time_ms == 500


class TestLegacyToInference:
    """Tests for legacy_to_inference transformation."""

    def test_basic_conversion(self, sample_legacy_request):
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

    def test_horizon_from_forecast_size(self, sample_legacy_request):
        """Horizon length should come from forecast_period_size."""
        result = legacy_to_inference(sample_legacy_request)

        assert result.horizon.length == sample_legacy_request.forecast_period_size

    def test_source_parameter(self, sample_legacy_request):
        """Source parameter should be used."""
        result = legacy_to_inference(
            sample_legacy_request,
            source=DataSource.YAHOO,
        )

        assert result.context.source == DataSource.YAHOO

    def test_period_parameter(self, sample_legacy_request):
        """Period parameter should be used."""
        result = legacy_to_inference(
            sample_legacy_request,
            period=Period.WEEK_1,
        )

        assert result.context.period == Period.WEEK_1
        assert result.horizon.period == Period.WEEK_1

    def test_as_of_date_used(self, sample_legacy_request):
        """as_of_date should be used as context end date."""
        result = legacy_to_inference(sample_legacy_request)

        assert result.context.end_date == "2025-12-30"

    def test_default_source_influxdb(self, sample_legacy_request):
        """Default source should be influxdb."""
        result = legacy_to_inference(sample_legacy_request)

        assert result.context.source == DataSource.INFLUXDB

    def test_request_id_generated(self, sample_legacy_request):
        """New request should have auto-generated request_id."""
        result = legacy_to_inference(sample_legacy_request)

        assert result.request_id is not None
        assert len(result.request_id) == 36


class TestInferenceToLegacy:
    """Tests for inference_to_legacy transformation."""

    def test_basic_conversion(self, sample_inference_response):
        """New response should convert to legacy format."""
        result = inference_to_legacy(sample_inference_response)

        assert isinstance(result, LegacyForecastResponse)
        assert result.name == sample_inference_response.ticker
        assert len(result.forecast) == len(sample_inference_response.forecast.values)

    def test_forecast_values_preserved(self, sample_inference_response):
        """Forecast values should be preserved exactly."""
        result = inference_to_legacy(sample_inference_response)

        assert result.forecast == sample_inference_response.forecast.values

    def test_success_message(self, sample_inference_response):
        """Message should be 'Success'."""
        result = inference_to_legacy(sample_inference_response)

        assert result.message == "Success"


# =============================================================================
# GAP-15 ERROR PATH TESTS
# =============================================================================

class TestChronosToInferenceErrors:
    """Tests for ComputationError in chronos_to_inference."""

    def test_no_median_or_mean_raises(self, sample_inference_request):
        """Response missing both median and mean should raise ComputationError."""
        bad_response = {"prediction": {"quantiles": {"10": [1.0]}}}
        with pytest.raises(ComputationError) as exc_info:
            chronos_to_inference(bad_response, sample_inference_request, 100)
        assert "missing forecast values" in exc_info.value.message

    def test_empty_median_and_mean_raises(self, sample_inference_request):
        """Response with empty median and mean lists should raise ComputationError."""
        bad_response = {"prediction": {"median": [], "mean": []}}
        with pytest.raises(ComputationError):
            chronos_to_inference(bad_response, sample_inference_request, 100)


class TestTimesFMToInferenceErrors:
    """Tests for ComputationError in timesfm_to_inference."""

    def test_missing_point_forecast_key_raises(self, sample_inference_request):
        """Response missing point_forecast key should raise ComputationError."""
        bad_response = {"other_key": [1.0]}
        with pytest.raises(ComputationError) as exc_info:
            timesfm_to_inference(bad_response, sample_inference_request, 100)
        assert "missing 'point_forecast'" in exc_info.value.message

    def test_empty_point_forecast_list_raises(self, sample_inference_request):
        """Empty point_forecast list should raise ComputationError."""
        bad_response = {"point_forecast": []}
        with pytest.raises(ComputationError) as exc_info:
            timesfm_to_inference(bad_response, sample_inference_request, 100)
        assert "empty" in exc_info.value.message.lower()

    def test_empty_inner_forecast_raises(self, sample_inference_request):
        """point_forecast: [[]] should raise ComputationError."""
        bad_response = {"point_forecast": [[]]}
        with pytest.raises(ComputationError) as exc_info:
            timesfm_to_inference(bad_response, sample_inference_request, 100)
        assert "empty" in exc_info.value.message.lower()
