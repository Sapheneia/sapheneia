"""
Unit tests for forecast.core.legacy_service

Tests service layer with mocked HTTP dependencies.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, Mock, patch
from forecast.core.legacy_service import LegacyForecastService
from forecast.core.legacy_schema import (
    AleutianForecastRequest,
    AleutianForecastResponse,
    ChronosInferenceResponse,
)


class TestLegacyForecastServiceInit:
    """Test LegacyForecastService initialization."""

    def test_initialization(self):
        """Test service initializes with correct URLs."""
        service = LegacyForecastService()
        
        assert service.base_url.startswith("http://localhost:")
        assert service.data_service_url == "http://sapheneia-data:8000"
        assert service.timeout == 300.0

    @patch('forecast.core.legacy_service.settings')
    def test_uses_settings_port(self, mock_settings):
        """Test that service uses port from settings."""
        mock_settings.API_PORT = 9999
        mock_settings.API_SECRET_KEY = "test_key"
        
        service = LegacyForecastService()
        
        assert service.base_url == "http://localhost:9999"


class TestEnsureModelInitialized:
    """Test model initialization logic."""

    @pytest.mark.asyncio
    async def test_already_initialized(self):
        """Test that already-initialized models are not reinitialized."""
        service = LegacyForecastService()
        
        # Mock httpx client
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"model_status": "ready"}
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            request = AleutianForecastRequest(
                name="SPY",
                context_period_size=90,
                forecast_period_size=10,
                model="amazon/chronos-t5-tiny"
            )
            
            await service._ensure_model_initialized("chronos", request)
            
            # Should check status but NOT call initialization
            mock_context.__aenter__.return_value.get.assert_called_once()
            # post should not be called
            assert not mock_context.__aenter__.return_value.post.called

    @pytest.mark.asyncio
    async def test_uninitialized_model(self):
        """Test that uninitialized models are initialized."""
        service = LegacyForecastService()
        
        # Mock status response (uninitialized)
        status_response = Mock()
        status_response.json.return_value = {"model_status": "uninitialized"}
        status_response.raise_for_status = Mock()
        
        # Mock init response
        init_response = Mock()
        init_response.json.return_value = {"status": "ready"}
        init_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=status_response)
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=init_response)
            mock_client.return_value = mock_context
            
            request = AleutianForecastRequest(
                name="SPY",
                context_period_size=90,
                forecast_period_size=10,
                model="amazon/chronos-t5-tiny"
            )
            
            await service._ensure_model_initialized("chronos", request)
            
            # Should call both status and init
            mock_context.__aenter__.return_value.get.assert_called_once()
            mock_context.__aenter__.return_value.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_chronos_init_payload(self):
        """Test that Chronos initialization includes model_variant."""
        service = LegacyForecastService()
        
        status_response = Mock()
        status_response.json.return_value = {"model_status": "uninitialized"}
        status_response.raise_for_status = Mock()
        
        init_response = Mock()
        init_response.json.return_value = {"status": "ready"}
        init_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=status_response)
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=init_response)
            mock_client.return_value = mock_context
            
            request = AleutianForecastRequest(
                name="SPY",
                context_period_size=90,
                forecast_period_size=10,
                model="amazon/chronos-t5-tiny"
            )
            
            await service._ensure_model_initialized("chronos", request)
            
            # Check that post was called with model_variant
            call_args = mock_context.__aenter__.return_value.post.call_args
            assert call_args[1]['json'] == {"model_variant": "amazon/chronos-t5-tiny"}


class TestFetchHistoricalData:
    """Test historical data fetching."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        """Test successful data fetch from data service."""
        service = LegacyForecastService()
        
        # Mock response from data service
        mock_response = Mock()
        mock_response.json.return_value = {
            "ticker": "SPY",
            "data": [
                {"time": "2023-01-01", "close": 450.0},
                {"time": "2023-01-02", "close": 451.0},
                {"time": "2023-01-03", "close": 452.0},
            ]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            prices = await service._fetch_historical_data("SPY", 3)
            
            assert prices == [450.0, 451.0, 452.0]

    @pytest.mark.asyncio
    async def test_fetch_uses_query_endpoint(self):
        """Test that fetch uses /v1/data/query endpoint."""
        service = LegacyForecastService()
        
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"close": 450.0}]}
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            await service._fetch_historical_data("SPY", 90)
            
            # Check URL
            call_args = mock_context.__aenter__.return_value.post.call_args
            assert "/v1/data/query" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_fetch_request_format(self):
        """Test that fetch sends correct request format."""
        service = LegacyForecastService()
        
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"close": 450.0}]}
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            await service._fetch_historical_data("AAPL", 180)
            
            # Check payload
            call_args = mock_context.__aenter__.return_value.post.call_args
            assert call_args[1]['json'] == {"ticker": "AAPL", "days": 180}

    @pytest.mark.asyncio
    async def test_missing_data_field(self):
        """Test error handling when data field is missing."""
        service = LegacyForecastService()
        
        mock_response = Mock()
        mock_response.json.return_value = {"ticker": "SPY"}  # Missing 'data'
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            with pytest.raises(ValueError, match="missing 'data' field"):
                await service._fetch_historical_data("SPY", 90)


class TestRunChronosInference:
    """Test Chronos inference execution."""

    @pytest.mark.asyncio
    async def test_successful_inference(self):
        """Test successful Chronos inference."""
        service = LegacyForecastService()
        
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=90,
            forecast_period_size=10,
            model="amazon/chronos-t5-tiny"
        )
        prices = [450.0 + i * 0.1 for i in range(90)]
        
        # Mock Chronos API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "prediction": {
                "median": [455.0, 456.0, 457.0, 458.0, 459.0, 460.0, 461.0, 462.0, 463.0, 464.0],
                "mean": [454.9, 455.9, 456.9, 457.9, 458.9, 459.9, 460.9, 461.9, 462.9, 463.9],
                "quantiles": {},
                "samples": [],
                "metadata": {"inference_time_seconds": 2.45}
            }
        }
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            result = await service._run_chronos_inference(request, prices)
            
            assert isinstance(result, AleutianForecastResponse)
            assert result.name == "SPY"
            assert len(result.forecast) == 10
            assert result.forecast[0] == 455.0

    @pytest.mark.asyncio
    async def test_inference_endpoint_url(self):
        """Test that inference uses correct endpoint."""
        service = LegacyForecastService()
        
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=10,
            forecast_period_size=5,
            model="amazon/chronos-t5-tiny"
        )
        prices = [450.0] * 10
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "prediction": {
                "median": [455.0] * 5,
                "mean": [455.0] * 5,
                "quantiles": {},
                "samples": [],
                "metadata": {}
            }
        }
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            await service._run_chronos_inference(request, prices)
            
            call_args = mock_context.__aenter__.return_value.post.call_args
            assert "/forecast/v1/chronos/inference" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_inference_request_payload(self):
        """Test that inference sends correct request payload."""
        service = LegacyForecastService()
        
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=5,
            forecast_period_size=3,
            model="amazon/chronos-t5-tiny"
        )
        prices = [100.0, 101.0, 102.0, 103.0, 104.0]
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "prediction": {
                "median": [105.0, 106.0, 107.0],
                "mean": [105.0, 106.0, 107.0],
                "quantiles": {},
                "samples": [],
                "metadata": {}
            }
        }
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            await service._run_chronos_inference(request, prices)
            
            call_args = mock_context.__aenter__.return_value.post.call_args
            payload = call_args[1]['json']
            
            assert payload['context'] == prices
            assert payload['prediction_length'] == 3
            assert payload['num_samples'] == 20


class TestFullForecastPipeline:
    """Test complete forecast pipeline."""

    @pytest.mark.asyncio
    async def test_successful_forecast(self):
        """Test successful end-to-end forecast."""
        service = LegacyForecastService()
        
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=90,
            forecast_period_size=10,
            model="amazon/chronos-t5-tiny"
        )
        
        # Mock all HTTP responses
        status_response = Mock()
        status_response.json.return_value = {"model_status": "ready"}
        status_response.raise_for_status = Mock()
        
        data_response = Mock()
        data_response.json.return_value = {
            "data": [{"close": 450.0 + i * 0.1} for i in range(90)]
        }
        data_response.raise_for_status = Mock()
        
        inference_response = Mock()
        inference_response.json.return_value = {
            "prediction": {
                "median": [455.0 + i * 0.2 for i in range(10)],
                "mean": [454.9 + i * 0.2 for i in range(10)],
                "quantiles": {},
                "samples": [],
                "metadata": {"inference_time_seconds": 2.45}
            }
        }
        inference_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            # Setup mock to return different responses for different calls
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=status_response)
            mock_context.__aenter__.return_value.post = AsyncMock(
                side_effect=[data_response, inference_response]
            )
            mock_client.return_value = mock_context
            
            result = await service.forecast(request)
            
            assert isinstance(result, AleutianForecastResponse)
            assert result.name == "SPY"
            assert len(result.forecast) == 10
            assert result.message == "Success"

    @pytest.mark.asyncio
    async def test_unsupported_model_family(self):
        """Test error handling for unsupported model family."""
        service = LegacyForecastService()
        
        # This will fail at determine_model_family
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=90,
            forecast_period_size=10,
            model="unknown/mysterious-model"
        )
        
        with pytest.raises(ValueError, match="Unknown model family"):
            await service.forecast(request)

    @pytest.mark.asyncio
    async def test_http_error_propagation(self):
        """Test that HTTP errors are propagated correctly."""
        service = LegacyForecastService()
        
        request = AleutianForecastRequest(
            name="SPY",
            context_period_size=90,
            forecast_period_size=10,
            model="amazon/chronos-t5-tiny"
        )
        
        # Mock status check to fail
        status_response = Mock()
        status_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error",
            request=Mock(),
            response=Mock(status_code=500)
        )
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=status_response)
            mock_client.return_value = mock_context
            
            with pytest.raises(httpx.HTTPStatusError):
                await service.forecast(request)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
