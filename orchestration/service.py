"""
Inference Service

Orchestration layer for handling inference requests. Routes to appropriate
model backends and handles request/response transformation.

Architecture:
    InferenceRequest -> InferenceService -> Model Backend -> InferenceResponse

This service:
- Does NOT fetch data (Aleutian/orchestrator provides data)
- Routes to the correct model based on model family
- Transforms between unified and model-specific formats
- Tracks inference timing for metadata
"""

import logging
import time
import httpx
from typing import Optional

from .schema import (
    InferenceRequest,
    InferenceResponse,
    LegacyForecastRequest,
    LegacyForecastResponse,
    Period,
    DataSource,
)
from .adapters import (
    determine_model_family,
    get_model_endpoint,
    inference_to_chronos,
    chronos_to_inference,
    inference_to_timesfm,
    timesfm_to_inference,
    legacy_to_inference,
    inference_to_legacy,
)

logger = logging.getLogger(__name__)


class InferenceService:
    """
    Handles unified inference requests from Aleutian.

    This service is a pure inference engine - it does NOT:
    - Query databases
    - Fetch historical data
    - Store results

    It ONLY:
    - Accepts data from the orchestrator
    - Routes to appropriate model backend
    - Returns forecasts
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        """
        Initialize inference service.

        Args:
            base_url: Base URL for model endpoints
            api_key: Optional API key for authentication
        """
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = 300.0  # 5 minutes for model operations

    async def predict(self, request: InferenceRequest) -> InferenceResponse:
        """
        Run inference on the provided context data.

        Main entry point for all inference requests.

        Args:
            request: Unified inference request with context data

        Returns:
            Unified inference response with forecast

        Raises:
            ValueError: If model family is unknown or unsupported
            httpx.HTTPError: If model backend call fails
        """
        logger.info("=" * 80)
        logger.info("INFERENCE REQUEST RECEIVED")
        logger.info("=" * 80)
        logger.info(f"  Request ID: {request.request_id}")
        logger.info(f"  Ticker: {request.ticker}")
        logger.info(f"  Model: {request.model}")
        logger.info(f"  Context Length: {len(request.context.values)}")
        logger.info(f"  Context Period: {request.context.period}")
        logger.info(f"  Context Source: {request.context.source}")
        logger.info(f"  Context Range: {request.context.start_date} to {request.context.end_date}")
        logger.info(f"  Horizon: {request.horizon.length} x {request.horizon.period}")
        logger.info("=" * 80)

        # Determine model family
        model_family = determine_model_family(request.model)
        logger.info(f"Model family: {model_family}")

        # Start timing
        start_time = time.time()

        # Route to appropriate handler
        if model_family == "chronos":
            response = await self._run_chronos_inference(request)
        elif model_family == "timesfm":
            response = await self._run_timesfm_inference(request)
        else:
            # For other models, attempt generic chronos-style inference
            logger.warning(f"Model family {model_family} using generic handler")
            response = await self._run_chronos_inference(request)

        # Log response
        logger.info("=" * 80)
        logger.info("INFERENCE RESPONSE")
        logger.info("=" * 80)
        logger.info(f"  Request ID: {response.request_id}")
        logger.info(f"  Response ID: {response.response_id}")
        logger.info(f"  Forecast Length: {len(response.forecast.values)}")
        logger.info(f"  Forecast Range: {response.forecast.start_date} to {response.forecast.end_date}")
        logger.info(f"  Inference Time: {response.metadata.inference_time_ms}ms")
        logger.info("=" * 80)

        return response

    async def _run_chronos_inference(self, request: InferenceRequest) -> InferenceResponse:
        """
        Execute Chronos model inference.

        Args:
            request: Unified inference request

        Returns:
            Unified inference response
        """
        start_time = time.time()

        # Transform to Chronos format
        chronos_request = inference_to_chronos(request)

        logger.info(f"Calling Chronos endpoint: {self.base_url}/forecast/v1/chronos/inference")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            resp = await client.post(
                f"{self.base_url}/forecast/v1/chronos/inference",
                json=chronos_request,
                headers=headers,
            )
            resp.raise_for_status()
            chronos_data = resp.json()

        inference_time_ms = int((time.time() - start_time) * 1000)

        # Transform to unified response
        return chronos_to_inference(chronos_data, request, inference_time_ms)

    async def _run_timesfm_inference(self, request: InferenceRequest) -> InferenceResponse:
        """
        Execute TimesFM model inference.

        Uses direct service layer call since TimesFM has different API.

        Args:
            request: Unified inference request

        Returns:
            Unified inference response
        """
        start_time = time.time()

        # Transform to TimesFM format
        timesfm_request = inference_to_timesfm(request)

        logger.info("Running TimesFM inference via service layer")

        # Import and call TimesFM service directly
        try:
            from forecast.models.timesfm20.services import model as timesfm_model_service
            import asyncio

            loop = asyncio.get_event_loop()
            results_dict = await loop.run_in_executor(
                None,
                timesfm_model_service.run_inference,
                timesfm_request["target_inputs"],
                timesfm_request["covariates"],
                timesfm_request["parameters"],
            )

            inference_time_ms = int((time.time() - start_time) * 1000)

            # Transform to unified response
            return timesfm_to_inference(results_dict, request, inference_time_ms)

        except ImportError:
            logger.warning("TimesFM service not available, falling back to HTTP")
            return await self._run_timesfm_http(request, start_time)

    async def _run_timesfm_http(self, request: InferenceRequest, start_time: float) -> InferenceResponse:
        """
        Fallback HTTP call for TimesFM when service layer not available.
        """
        timesfm_request = inference_to_timesfm(request)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            resp = await client.post(
                f"{self.base_url}/forecast/v1/timesfm20/inference",
                json=timesfm_request,
                headers=headers,
            )
            resp.raise_for_status()
            timesfm_data = resp.json()

        inference_time_ms = int((time.time() - start_time) * 1000)
        return timesfm_to_inference(timesfm_data, request, inference_time_ms)


class LegacyCompatService:
    """
    Backwards-compatible service that handles legacy AleutianForecastRequest.

    Wraps InferenceService to provide the old API contract.
    """

    def __init__(self, inference_service: InferenceService):
        self.inference_service = inference_service

    async def forecast(
        self,
        request: LegacyForecastRequest,
        source: DataSource = DataSource.INFLUXDB,
        period: Period = Period.DAY_1,
    ) -> LegacyForecastResponse:
        """
        Handle legacy forecast request.

        Converts to new format, runs inference, converts back.

        Args:
            request: Legacy format request
            source: Data source (for metadata)
            period: Data period (for metadata)

        Returns:
            Legacy format response
        """
        logger.info("=" * 80)
        logger.info("LEGACY FORECAST REQUEST (Converting to new format)")
        logger.info("=" * 80)
        logger.info(f"  Ticker: {request.name}")
        logger.info(f"  Model: {request.model}")
        logger.info(f"  Context Size: {request.context_period_size}")
        logger.info(f"  Horizon: {request.forecast_period_size}")
        logger.info(f"  Data Points: {len(request.recent_data)}")
        logger.info("=" * 80)

        # Convert to new format
        inference_request = legacy_to_inference(request, source, period)

        # Run inference
        inference_response = await self.inference_service.predict(inference_request)

        # Convert back to legacy format
        legacy_response = inference_to_legacy(inference_response)

        logger.info(f"Legacy response: ticker={legacy_response.name}, forecast_len={len(legacy_response.forecast)}")

        return legacy_response
