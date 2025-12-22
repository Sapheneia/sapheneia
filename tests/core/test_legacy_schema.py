"""
Unit tests for forecast.core.legacy_schema

Tests Pydantic model validation for all data contracts.
"""

import pytest
from pydantic import ValidationError
from forecast.core.legacy_schema import (
    AleutianForecastRequest,
    AleutianForecastResponse,
    ChronosInferenceRequest,
    ChronosInferenceResponse,
)


class TestAleutianForecastRequest:
    """Test AleutianForecastRequest validation."""

    def test_valid_request(self):
        """Test creating a valid forecast request."""
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=90,
            forecast_period_size=10,
            model="amazon/chronos-t5-tiny"
        )
        assert request.name == "SPY"
        assert request.context_period_size == 90
        assert request.forecast_period_size == 10
        assert request.model == "amazon/chronos-t5-tiny"

    def test_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AleutianForecastRequest(
                name="SPY",
                context_period_size=90
                # Missing forecast_period_size and model
            )
        errors = exc_info.value.errors()
        assert any(e['loc'] == ('forecast_period_size',) for e in errors)
        assert any(e['loc'] == ('model',) for e in errors)

    def test_context_period_size_validation(self):
        """Test that context_period_size must be positive."""
        with pytest.raises(ValidationError) as exc_info:
            AleutianForecastRequest(
                name="SPY",
                context_period_size=0,  # Invalid: must be > 0
                forecast_period_size=10,
                model="amazon/chronos-t5-tiny"
            )
        assert 'greater than 0' in str(exc_info.value)

    def test_forecast_period_size_validation(self):
        """Test that forecast_period_size must be positive."""
        with pytest.raises(ValidationError) as exc_info:
            AleutianForecastRequest(
                name="SPY",
                context_period_size=90,
                forecast_period_size=-5,  # Invalid: must be > 0
                model="amazon/chronos-t5-tiny"
            )
        assert 'greater than 0' in str(exc_info.value)

    def test_json_schema_example(self):
        """Test that the example in json_schema is valid."""
        example = {
            "name": "SPY",
            "context_period_size": 90,
            "forecast_period_size": 30,
            "model": "amazon/chronos-t5-tiny"
        }
        request = AleutianForecastRequest(**example)
        assert request.model_dump() == example


class TestAleutianForecastResponse:
    """Test AleutianForecastResponse validation."""

    def test_valid_response(self):
        """Test creating a valid forecast response."""
        response = AleutianForecastResponse(
            name="SPY",
            forecast=[450.2, 451.5, 452.8],
            message="Success"
        )
        assert response.name == "SPY"
        assert response.forecast == [450.2, 451.5, 452.8]
        assert response.message == "Success"

    def test_default_message(self):
        """Test that message has a default value."""
        response = AleutianForecastResponse(
            name="SPY",
            forecast=[450.2, 451.5]
        )
        assert response.message == "Success"

    def test_empty_forecast(self):
        """Test that forecast can be empty list."""
        response = AleutianForecastResponse(
            name="SPY",
            forecast=[]
        )
        assert response.forecast == []

    def test_json_schema_example(self):
        """Test that the example in json_schema is valid."""
        example = {
            "name": "SPY",
            "forecast": [450.2, 451.5, 452.8, 453.1],
            "message": "Success"
        }
        response = AleutianForecastResponse(**example)
        assert response.name == example["name"]
        assert response.forecast == example["forecast"]
        assert response.message == example["message"]


class TestChronosInferenceRequest:
    """Test ChronosInferenceRequest validation."""

    def test_valid_request(self):
        """Test creating a valid Chronos inference request."""
        request = ChronosInferenceRequest(
            context=[1.0, 2.0, 3.0, 4.0, 5.0],
            prediction_length=10,
            num_samples=20,
            temperature=1.0,
            top_k=50,
            top_p=1.0
        )
        assert request.context == [1.0, 2.0, 3.0, 4.0, 5.0]
        assert request.prediction_length == 10
        assert request.num_samples == 20

    def test_default_values(self):
        """Test that optional fields have correct defaults."""
        request = ChronosInferenceRequest(
            context=[1.0, 2.0, 3.0],
            prediction_length=5
        )
        assert request.num_samples == 20
        assert request.temperature == 1.0
        assert request.top_k == 50
        assert request.top_p == 1.0

    def test_prediction_length_validation(self):
        """Test that prediction_length must be positive."""
        with pytest.raises(ValidationError):
            ChronosInferenceRequest(
                context=[1.0, 2.0],
                prediction_length=0  # Invalid
            )

    def test_num_samples_validation(self):
        """Test that num_samples must be positive."""
        with pytest.raises(ValidationError):
            ChronosInferenceRequest(
                context=[1.0, 2.0],
                prediction_length=5,
                num_samples=-1  # Invalid
            )

    def test_temperature_validation(self):
        """Test that temperature must be positive."""
        with pytest.raises(ValidationError):
            ChronosInferenceRequest(
                context=[1.0, 2.0],
                prediction_length=5,
                temperature=0.0  # Invalid: must be > 0
            )

    def test_top_p_validation(self):
        """Test that top_p must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ChronosInferenceRequest(
                context=[1.0, 2.0],
                prediction_length=5,
                top_p=1.5  # Invalid: must be <= 1.0
            )


class TestChronosInferenceResponse:
    """Test ChronosInferenceResponse validation."""

    def test_valid_response(self):
        """Test creating a valid Chronos inference response."""
        response = ChronosInferenceResponse(
            median=[450.2, 451.5, 452.8],
            mean=[450.1, 451.4, 452.9],
            quantiles={
                "10": [448.0, 449.0, 450.0],
                "50": [450.2, 451.5, 452.8],
                "90": [452.0, 453.0, 454.0]
            },
            samples=[
                [449.0, 450.0, 451.0],
                [450.0, 451.0, 452.0],
                [451.0, 452.0, 453.0]
            ],
            metadata={
                "context_length": 90,
                "prediction_length": 3,
                "num_samples": 3,
                "model_variant": "amazon/chronos-t5-tiny",
                "inference_time_seconds": 2.45
            }
        )
        assert response.median == [450.2, 451.5, 452.8]
        assert response.mean == [450.1, 451.4, 452.9]
        assert len(response.quantiles) == 3
        assert len(response.samples) == 3
        assert response.metadata["model_variant"] == "amazon/chronos-t5-tiny"

    def test_default_values(self):
        """Test that optional fields have correct defaults."""
        response = ChronosInferenceResponse(
            median=[450.2, 451.5],
            mean=[450.1, 451.4]
        )
        assert response.quantiles == {}
        assert response.samples == []
        assert response.metadata == {}

    def test_empty_median(self):
        """Test that median can be empty."""
        response = ChronosInferenceResponse(
            median=[],
            mean=[]
        )
        assert response.median == []
        assert response.mean == []


class TestCrossModelValidation:
    """Test interactions between models."""

    def test_request_response_consistency(self):
        """Test that request and response forecast lengths match."""
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=90,
            forecast_period_size=10,
            model="amazon/chronos-t5-tiny"
        )
        
        # Response should have forecast length matching request
        response = AleutianForecastResponse(
            name=request.name,
            forecast=[450.0 + i for i in range(request.forecast_period_size)]
        )
        
        assert len(response.forecast) == request.forecast_period_size
        assert response.name == request.name

    def test_chronos_to_aleutian_mapping(self):
        """Test that Chronos response can map to AleutianForecastResponse."""
        chronos_response = ChronosInferenceResponse(
            median=[450.2, 451.5, 452.8],
            mean=[450.1, 451.4, 452.9]
        )
        
        # Map to AleutianForecastResponse
        aleutian_response = AleutianForecastResponse(
            name="SPY",
            forecast=chronos_response.median
        )
        
        assert aleutian_response.forecast == chronos_response.median


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
