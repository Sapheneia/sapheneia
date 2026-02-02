"""
Tests for orchestration/service.py

Tests inference service with mocked HTTP calls.
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock, MagicMock
import httpx

from orchestration.service import InferenceService, LegacyCompatService
from orchestration.schema import (
    InferenceRequest,
    InferenceResponse,
    LegacyForecastResponse,
    Period,
    DataSource,
)


class TestInferenceServiceInit:
    """Tests for InferenceService initialization."""

    def test_default_initialization(self):
        """Service should initialize with defaults."""
        service = InferenceService()
        assert service.base_url == "http://localhost:8000"
        assert service.api_key is None
        assert service.timeout == 300.0

    def test_custom_base_url(self):
        """Service should accept custom base URL."""
        service = InferenceService(base_url="http://custom:9000")
        assert service.base_url == "http://custom:9000"

    def test_custom_api_key(self):
        """Service should accept API key."""
        service = InferenceService(api_key="test-key-123")
        assert service.api_key == "test-key-123"

    def test_env_vars_for_service_urls(self, monkeypatch):
        """Service should use environment variables for model URLs."""
        monkeypatch.setenv("CHRONOS_SERVICE_URL", "http://chronos:8000")
        monkeypatch.setenv("TIMESFM_SERVICE_URL", "http://timesfm:8000")

        service = InferenceService()

        assert service.chronos_url == "http://chronos:8000"
        assert service.timesfm_url == "http://timesfm:8000"


class TestInferenceServicePredict:
    """Tests for InferenceService.predict method."""

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
        mock_chronos_response,
    ):
        """Chronos models should route to Chronos handler."""
        with patch.object(
            service,
            "_run_chronos_inference",
            new_callable=AsyncMock,
        ) as mock_chronos:
            mock_response = Mock(spec=InferenceResponse)
            mock_response.request_id = sample_inference_request.request_id
            mock_response.response_id = "test-response"
            mock_response.forecast = Mock()
            mock_response.forecast.values = [1.0, 2.0, 3.0]
            mock_response.forecast.start_date = "2025-12-31"
            mock_response.forecast.end_date = "2026-01-02"
            mock_response.metadata = Mock()
            mock_response.metadata.inference_time_ms = 100
            mock_chronos.return_value = mock_response

            result = await service.predict(sample_inference_request)

            mock_chronos.assert_called_once_with(sample_inference_request)
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_predict_routes_to_timesfm(
        self,
        service,
        sample_inference_request,
    ):
        """TimesFM models should route to TimesFM handler."""
        sample_inference_request.model = "google/timesfm-2.0"

        with patch.object(
            service,
            "_run_timesfm_inference",
            new_callable=AsyncMock,
        ) as mock_timesfm:
            mock_response = Mock(spec=InferenceResponse)
            mock_response.request_id = sample_inference_request.request_id
            mock_response.response_id = "test-response"
            mock_response.forecast = Mock()
            mock_response.forecast.values = [1.0, 2.0, 3.0]
            mock_response.forecast.start_date = "2025-12-31"
            mock_response.forecast.end_date = "2026-01-02"
            mock_response.metadata = Mock()
            mock_response.metadata.inference_time_ms = 100
            mock_timesfm.return_value = mock_response

            await service.predict(sample_inference_request)

            mock_timesfm.assert_called_once()

    @pytest.mark.asyncio
    async def test_predict_unknown_model_uses_generic(
        self,
        service,
        sample_inference_request,
    ):
        """Unknown models should fall back to generic (Chronos) handler."""
        sample_inference_request.model = "salesforce/moirai-1.1-R-small"

        with patch.object(
            service,
            "_run_chronos_inference",
            new_callable=AsyncMock,
        ) as mock_chronos:
            mock_response = Mock(spec=InferenceResponse)
            mock_response.request_id = sample_inference_request.request_id
            mock_response.response_id = "test-response"
            mock_response.forecast = Mock()
            mock_response.forecast.values = [1.0, 2.0, 3.0]
            mock_response.forecast.start_date = "2025-12-31"
            mock_response.forecast.end_date = "2026-01-02"
            mock_response.metadata = Mock()
            mock_response.metadata.inference_time_ms = 100
            mock_chronos.return_value = mock_response

            await service.predict(sample_inference_request)

            mock_chronos.assert_called_once()


class TestChronosInference:
    """Tests for Chronos inference method."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return InferenceService(
            base_url="http://test:8000",
            api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_chronos_calls_correct_endpoint(
        self,
        service,
        sample_inference_request,
        mock_chronos_response,
    ):
        """Chronos should call the /forecast/v1/inference endpoint."""
        mock_response = Mock()
        mock_response.json.return_value = mock_chronos_response
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await service._run_chronos_inference(sample_inference_request)

            # Verify endpoint
            call_args = mock_instance.post.call_args
            assert "/forecast/v1/inference" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_chronos_includes_auth_header(
        self,
        service,
        sample_inference_request,
        mock_chronos_response,
    ):
        """Chronos should include Authorization header when API key set."""
        mock_response = Mock()
        mock_response.json.return_value = mock_chronos_response
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await service._run_chronos_inference(sample_inference_request)

            call_args = mock_instance.post.call_args
            headers = call_args[1]["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_chronos_http_error_propagates(
        self,
        service,
        sample_inference_request,
    ):
        """HTTP errors should propagate from Chronos."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=Mock(status_code=500),
            )
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(httpx.HTTPStatusError):
                await service._run_chronos_inference(sample_inference_request)

    @pytest.mark.asyncio
    async def test_chronos_returns_inference_response(
        self,
        service,
        sample_inference_request,
        mock_chronos_response,
    ):
        """Chronos should return an InferenceResponse."""
        mock_response = Mock()
        mock_response.json.return_value = mock_chronos_response
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await service._run_chronos_inference(sample_inference_request)

            assert isinstance(result, InferenceResponse)
            assert result.request_id == sample_inference_request.request_id


class TestTimesFMInference:
    """Tests for TimesFM inference methods."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return InferenceService(
            base_url="http://test:8000",
            api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_timesfm_http_fallback(
        self,
        service,
        sample_inference_request,
        mock_timesfm_response,
    ):
        """TimesFM should fall back to HTTP when service unavailable."""
        sample_inference_request.model = "google/timesfm-2.0"

        mock_response = Mock()
        mock_response.json.return_value = mock_timesfm_response
        mock_response.raise_for_status = Mock()

        # Patch the import to fail (service not available)
        with patch.object(
            service,
            "_run_timesfm_http",
            new_callable=AsyncMock,
        ) as mock_http:
            mock_http_response = Mock(spec=InferenceResponse)
            mock_http_response.request_id = sample_inference_request.request_id
            mock_http.return_value = mock_http_response

            # Simulate ImportError for direct service
            with patch.dict("sys.modules", {"forecast.models.timesfm20.services": None}):
                with patch("builtins.__import__", side_effect=ImportError("No module")):
                    result = await service._run_timesfm_inference(sample_inference_request)

            mock_http.assert_called_once()

    @pytest.mark.asyncio
    async def test_timesfm_http_calls_endpoint(
        self,
        service,
        sample_inference_request,
        mock_timesfm_response,
    ):
        """TimesFM HTTP should call the correct endpoint."""
        sample_inference_request.model = "google/timesfm-2.0"

        mock_response = Mock()
        mock_response.json.return_value = mock_timesfm_response
        mock_response.raise_for_status = Mock()

        import time
        start_time = time.time()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await service._run_timesfm_http(sample_inference_request, start_time)

            call_args = mock_instance.post.call_args
            assert "/timesfm20/inference" in call_args[0][0]


class TestServiceTimeout:
    """Tests for service timeout configuration."""

    def test_default_timeout(self):
        """Default timeout should be 300 seconds."""
        service = InferenceService()
        assert service.timeout == 300.0

    def test_custom_timeout_via_constructor(self):
        """Timeout should be configurable via constructor."""
        service = InferenceService(timeout=60.0)
        assert service.timeout == 60.0

    def test_timeout_from_env_var(self, monkeypatch):
        """Timeout should be configurable via INFERENCE_TIMEOUT env var."""
        monkeypatch.setenv("INFERENCE_TIMEOUT", "120.0")
        service = InferenceService()
        assert service.timeout == 120.0

    def test_constructor_timeout_overrides_env_var(self, monkeypatch):
        """Constructor timeout should take precedence over env var."""
        monkeypatch.setenv("INFERENCE_TIMEOUT", "120.0")
        service = InferenceService(timeout=30.0)
        assert service.timeout == 30.0

    def test_invalid_env_var_uses_default(self, monkeypatch):
        """Invalid INFERENCE_TIMEOUT should fall back to default."""
        monkeypatch.setenv("INFERENCE_TIMEOUT", "not-a-number")
        service = InferenceService()
        assert service.timeout == 300.0  # DEFAULT_TIMEOUT

    def test_none_timeout_uses_env_var(self, monkeypatch):
        """Explicit None timeout should use env var."""
        monkeypatch.setenv("INFERENCE_TIMEOUT", "90.0")
        service = InferenceService(timeout=None)
        assert service.timeout == 90.0

    @pytest.mark.asyncio
    async def test_timeout_used_in_http_client(
        self,
        sample_inference_request,
        mock_chronos_response,
    ):
        """Timeout should be passed to httpx client."""
        service = InferenceService()

        mock_response = Mock()
        mock_response.json.return_value = mock_chronos_response
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await service._run_chronos_inference(sample_inference_request)

            # Verify timeout was passed to AsyncClient
            mock_client.assert_called_with(timeout=300.0)

    @pytest.mark.asyncio
    async def test_custom_timeout_used_in_http_client(
        self,
        sample_inference_request,
        mock_chronos_response,
    ):
        """Custom timeout should be passed to httpx client."""
        service = InferenceService(timeout=45.0)

        mock_response = Mock()
        mock_response.json.return_value = mock_chronos_response
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await service._run_chronos_inference(sample_inference_request)

            # Verify custom timeout was passed to AsyncClient
            mock_client.assert_called_with(timeout=45.0)


class TestLegacyCompatService:
    """Tests for LegacyCompatService class."""

    @pytest.fixture
    def legacy_service(self):
        """Create legacy compat service."""
        inference_service = InferenceService()
        return LegacyCompatService(inference_service)

    @pytest.mark.asyncio
    async def test_forecast_converts_request(
        self,
        legacy_service,
        sample_legacy_request,
        sample_inference_response,
    ):
        """Legacy forecast should convert request format."""
        with patch.object(
            legacy_service.inference_service,
            "predict",
            new_callable=AsyncMock,
        ) as mock_predict:
            mock_predict.return_value = sample_inference_response

            result = await legacy_service.forecast(sample_legacy_request)

            # Verify predict was called with InferenceRequest
            mock_predict.assert_called_once()
            call_arg = mock_predict.call_args[0][0]
            assert isinstance(call_arg, InferenceRequest)
            assert call_arg.ticker == sample_legacy_request.name

    @pytest.mark.asyncio
    async def test_forecast_returns_legacy_response(
        self,
        legacy_service,
        sample_legacy_request,
        sample_inference_response,
    ):
        """Legacy forecast should return LegacyForecastResponse."""
        with patch.object(
            legacy_service.inference_service,
            "predict",
            new_callable=AsyncMock,
        ) as mock_predict:
            mock_predict.return_value = sample_inference_response

            result = await legacy_service.forecast(sample_legacy_request)

            assert isinstance(result, LegacyForecastResponse)
            assert result.name == sample_legacy_request.name
            assert result.message == "Success"

    @pytest.mark.asyncio
    async def test_forecast_uses_source_parameter(
        self,
        legacy_service,
        sample_legacy_request,
        sample_inference_response,
    ):
        """Legacy forecast should use source parameter."""
        with patch.object(
            legacy_service.inference_service,
            "predict",
            new_callable=AsyncMock,
        ) as mock_predict:
            mock_predict.return_value = sample_inference_response

            await legacy_service.forecast(
                sample_legacy_request,
                source=DataSource.YAHOO,
            )

            call_arg = mock_predict.call_args[0][0]
            assert call_arg.context.source == DataSource.YAHOO

    @pytest.mark.asyncio
    async def test_forecast_uses_period_parameter(
        self,
        legacy_service,
        sample_legacy_request,
        sample_inference_response,
    ):
        """Legacy forecast should use period parameter."""
        with patch.object(
            legacy_service.inference_service,
            "predict",
            new_callable=AsyncMock,
        ) as mock_predict:
            mock_predict.return_value = sample_inference_response

            await legacy_service.forecast(
                sample_legacy_request,
                period=Period.WEEK_1,
            )

            call_arg = mock_predict.call_args[0][0]
            assert call_arg.context.period == Period.WEEK_1
            assert call_arg.horizon.period == Period.WEEK_1


class TestServiceErrorHandling:
    """Tests for service error handling."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return InferenceService()

    @pytest.mark.asyncio
    async def test_unknown_model_raises_value_error(
        self,
        service,
        sample_inference_request,
    ):
        """Unknown model should raise ValueError."""
        sample_inference_request.model = "totally/unknown-model"

        with pytest.raises(ValueError) as exc_info:
            await service.predict(sample_inference_request)

        assert "Unknown model family" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connection_error_propagates(
        self,
        service,
        sample_inference_request,
    ):
        """Connection errors should propagate."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(httpx.ConnectError):
                await service._run_chronos_inference(sample_inference_request)
