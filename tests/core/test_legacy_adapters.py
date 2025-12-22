"""
Unit tests for forecast.core.legacy_adapters

Tests pure transformation functions for data conversion.
"""

import pytest
from forecast.core.legacy_adapters import (
    determine_model_family,
    get_model_base_path,
    aleutian_to_chronos,
    chronos_to_aleutian,
)
from forecast.core.legacy_schema import (
    AleutianForecastRequest,
    ChronosInferenceRequest,
    ChronosInferenceResponse,
    AleutianForecastResponse,
)


class TestDetermineModelFamily:
    """Test determine_model_family function."""

    def test_chronos_models(self):
        """Test recognition of Chronos models."""
        test_cases = [
            "amazon/chronos-t5-tiny",
            "amazon/chronos-t5-mini",
            "amazon/chronos-t5-small",
            "amazon/chronos-t5-base",
            "amazon/chronos-t5-large",
            "amazon/chronos-bolt-mini",
            "amazon/chronos-bolt-small",
            "amazon/chronos-bolt-base",
            "AMAZON/CHRONOS-T5-TINY",  # Case insensitive
            "custom-chronos-model",  # Contains chronos
        ]
        for model_name in test_cases:
            assert determine_model_family(model_name) == "chronos", \
                f"Failed for {model_name}"

    def test_timesfm_models(self):
        """Test recognition of TimesFM models."""
        test_cases = [
            "google/timesfm-2.0-500m-pytorch",
            "google/timesfm-1.0-200m",
            "TIMESFM-MODEL",  # Case insensitive
            "custom-timesfm",  # Contains timesfm
        ]
        for model_name in test_cases:
            assert determine_model_family(model_name) == "timesfm", \
                f"Failed for {model_name}"

    def test_moirai_models(self):
        """Test recognition of Moirai models."""
        test_cases = [
            "salesforce/moirai-1.1-base",
            "salesforce/moirai-1.0-large",
            "MOIRAI-MODEL",  # Case insensitive
        ]
        for model_name in test_cases:
            assert determine_model_family(model_name) == "moirai", \
                f"Failed for {model_name}"

    def test_granite_models(self):
        """Test recognition of Granite models."""
        test_cases = [
            "ibm/granite-timeseries-ttm",
            "GRANITE-MODEL",  # Case insensitive
        ]
        for model_name in test_cases:
            assert determine_model_family(model_name) == "granite", \
                f"Failed for {model_name}"

    def test_moment_models(self):
        """Test recognition of MOMENT models."""
        test_cases = [
            "autolab/moment-1-large",
            "MOMENT-MODEL",  # Case insensitive
        ]
        for model_name in test_cases:
            assert determine_model_family(model_name) == "moment", \
                f"Failed for {model_name}"

    def test_unknown_model(self):
        """Test that unknown models raise ValueError."""
        with pytest.raises(ValueError, match="Unknown model family"):
            determine_model_family("unknown/mysterious-model")

    def test_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown model family"):
            determine_model_family("")


class TestGetModelBasePath:
    """Test get_model_base_path function."""

    def test_chronos_path(self):
        """Test Chronos model path."""
        assert get_model_base_path("chronos") == "/forecast/v1/chronos"

    def test_timesfm_path(self):
        """Test TimesFM model path."""
        assert get_model_base_path("timesfm") == "/forecast/v1/timesfm20"

    def test_moirai_path(self):
        """Test Moirai model path."""
        assert get_model_base_path("moirai") == "/forecast/v1/moirai"

    def test_granite_path(self):
        """Test Granite model path."""
        assert get_model_base_path("granite") == "/forecast/v1/granite"

    def test_moment_path(self):
        """Test MOMENT model path."""
        assert get_model_base_path("moment") == "/forecast/v1/moment"

    def test_unknown_model_family(self):
        """Test that unknown model family raises ValueError."""
        with pytest.raises(ValueError, match="No base path for model family"):
            get_model_base_path("unknown")

    def test_case_sensitive(self):
        """Test that function is case-sensitive."""
        with pytest.raises(ValueError):
            get_model_base_path("CHRONOS")  # Must be lowercase


class TestAleutianToChronos:
    """Test aleutian_to_chronos transformation."""

    def test_basic_transformation(self):
        """Test basic request transformation."""
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=90,
            forecast_period_size=10,
            model="amazon/chronos-t5-tiny"
        )
        prices = [450.0 + i * 0.5 for i in range(90)]
        
        result = aleutian_to_chronos(request, prices)
        
        assert isinstance(result, ChronosInferenceRequest)
        assert result.context == prices
        assert result.prediction_length == 10
        assert result.num_samples == 20  # Default

    def test_default_sampling_parameters(self):
        """Test that default sampling parameters are set."""
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=50,
            forecast_period_size=5,
            model="amazon/chronos-t5-tiny"
        )
        prices = [100.0] * 50
        
        result = aleutian_to_chronos(request, prices)
        
        assert result.num_samples == 20
        assert result.temperature == 1.0
        assert result.top_k == 50
        assert result.top_p == 1.0

    def test_context_preservation(self):
        """Test that context data is preserved exactly."""
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=10,
            forecast_period_size=5,
            model="amazon/chronos-t5-tiny"
        )
        prices = [1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8, 9.9, 10.0]
        
        result = aleutian_to_chronos(request, prices)
        
        assert result.context == prices
        assert len(result.context) == 10

    def test_different_forecast_lengths(self):
        """Test various forecast horizon lengths."""
        prices = [100.0] * 200
        
        for horizon in [1, 5, 10, 20, 30, 50, 100]:
            request = AleutianForecastRequest(
                name="SPY",
                context_period_size=200,
                forecast_period_size=horizon,
                model="amazon/chronos-t5-tiny"
            )
            result = aleutian_to_chronos(request, prices)
            assert result.prediction_length == horizon


class TestChronosToAleutian:
    """Test chronos_to_aleutian transformation."""

    def test_basic_transformation(self):
        """Test basic response transformation."""
        chronos_response = ChronosInferenceResponse(
            median=[450.2, 451.5, 452.8],
            mean=[450.1, 451.4, 452.9],
            quantiles={"50": [450.2, 451.5, 452.8]},
            samples=[],
            metadata={}
        )
        
        result = chronos_to_aleutian(chronos_response, "SPY")
        
        assert isinstance(result, AleutianForecastResponse)
        assert result.name == "SPY"
        assert result.forecast == [450.2, 451.5, 452.8]  # Uses median
        assert result.message == "Success"

    def test_uses_median_not_mean(self):
        """Test that transformation uses median, not mean."""
        chronos_response = ChronosInferenceResponse(
            median=[450.0, 451.0, 452.0],
            mean=[449.0, 450.0, 451.0],  # Different from median
        )
        
        result = chronos_to_aleutian(chronos_response, "AAPL")
        
        assert result.forecast == chronos_response.median
        assert result.forecast != chronos_response.mean

    def test_ticker_preservation(self):
        """Test that ticker symbol is preserved correctly."""
        chronos_response = ChronosInferenceResponse(
            median=[100.0, 101.0],
            mean=[100.0, 101.0]
        )
        
        tickers = ["SPY", "AAPL", "MSFT", "GOOGL", "BTCUSDT"]
        for ticker in tickers:
            result = chronos_to_aleutian(chronos_response, ticker)
            assert result.name == ticker

    def test_empty_forecast(self):
        """Test handling of empty forecast."""
        chronos_response = ChronosInferenceResponse(
            median=[],
            mean=[]
        )
        
        result = chronos_to_aleutian(chronos_response, "SPY")
        
        assert result.forecast == []
        assert result.name == "SPY"

    def test_long_forecast(self):
        """Test handling of long forecasts."""
        long_median = [100.0 + i * 0.1 for i in range(252)]  # 1 year
        chronos_response = ChronosInferenceResponse(
            median=long_median,
            mean=long_median
        )
        
        result = chronos_to_aleutian(chronos_response, "SPY")
        
        assert len(result.forecast) == 252
        assert result.forecast == long_median


class TestEndToEndTransformation:
    """Test complete transformation pipeline."""

    def test_roundtrip_consistency(self):
        """Test that data flows correctly through transformations."""
        # 1. Start with AleutianLocal request
        aleutian_request = AleutianForecastRequest(
            name="SPY",
            context_period_size=90,
            forecast_period_size=10,
            model="amazon/chronos-t5-tiny"
        )
        
        # 2. Simulate historical prices
        historical_prices = [450.0 + i * 0.1 for i in range(90)]
        
        # 3. Transform to Chronos format
        chronos_request = aleutian_to_chronos(aleutian_request, historical_prices)
        
        # 4. Simulate Chronos response
        forecast_values = [455.0 + i * 0.2 for i in range(10)]
        chronos_response = ChronosInferenceResponse(
            median=forecast_values,
            mean=forecast_values,
            metadata={
                "context_length": 90,
                "prediction_length": 10
            }
        )
        
        # 5. Transform back to AleutianLocal format
        aleutian_response = chronos_to_aleutian(chronos_response, aleutian_request.name)
        
        # Verify consistency
        assert aleutian_response.name == aleutian_request.name
        assert len(aleutian_response.forecast) == aleutian_request.forecast_period_size
        assert aleutian_response.forecast == forecast_values

    def test_model_family_routing(self):
        """Test that model routing works with transformations."""
        models = [
            ("amazon/chronos-t5-tiny", "chronos"),
            ("google/timesfm-2.0-500m", "timesfm"),
            ("salesforce/moirai-1.1-base", "moirai"),
        ]
        
        for model_name, expected_family in models:
            request = AleutianForecastRequest(
                name="SPY",
                context_period_size=50,
                forecast_period_size=10,
                model=model_name
            )
            
            family = determine_model_family(request.model)
            assert family == expected_family
            
            base_path = get_model_base_path(family)
            assert base_path.startswith("/forecast/v1/")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_very_small_context(self):
        """Test transformation with minimal context."""
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=1,
            forecast_period_size=1,
            model="amazon/chronos-t5-tiny"
        )
        prices = [450.0]
        
        result = aleutian_to_chronos(request, prices)
        assert result.context == prices
        assert result.prediction_length == 1

    def test_very_large_context(self):
        """Test transformation with large context."""
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=2520,  # 10 years daily
            forecast_period_size=252,  # 1 year
            model="amazon/chronos-t5-tiny"
        )
        prices = [450.0] * 2520
        
        result = aleutian_to_chronos(request, prices)
        assert len(result.context) == 2520
        assert result.prediction_length == 252

    def test_single_forecast_point(self):
        """Test transformation with single forecast point."""
        chronos_response = ChronosInferenceResponse(
            median=[450.5],
            mean=[450.3]
        )
        
        result = chronos_to_aleutian(chronos_response, "SPY")
        assert len(result.forecast) == 1
        assert result.forecast[0] == 450.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
