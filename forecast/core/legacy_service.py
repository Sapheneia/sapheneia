"""
Legacy Forecast Service

Service layer for handling legacy /v1/timeseries/forecast requests
from AleutianLocal. Orchestrates model initialization, data fetching,
and inference execution.

Single Responsibility: This service ONLY handles the legacy API contract.
All data transformations are delegated to pure adapter functions.
"""

import logging
import httpx
from typing import List, Optional
from .config import settings
from .legacy_schema import (
    AleutianForecastRequest,
    AleutianForecastResponse,
    ChronosInferenceRequest,
    ChronosInferenceResponse,
)
from .legacy_adapters import (
    determine_model_family,
    get_model_base_path,
    aleutian_to_chronos,
    chronos_to_aleutian,
)

logger = logging.getLogger(__name__)


class LegacyForecastService:
    """
    Handles legacy forecast requests from AleutianLocal.

    This service acts as an orchestrator, coordinating:
    1. Model initialization
    2. Historical data retrieval
    3. Model-specific inference
    4. Response transformation

    All HTTP calls use async/await for non-blocking I/O.
    """

    def __init__(self):
        """Initialize service with API endpoints."""
        self.base_url = f"http://localhost:{settings.API_PORT}"
        self.data_service_url = "http://sapheneia-data:8000"  # Internal docker network
        self.timeout = 300.0  # 5 minutes for model operations

    async def forecast(
        self,
        request: AleutianForecastRequest
    ) -> AleutianForecastResponse:
        """
        Process forecast request from AleutianLocal.

        Single responsibility: Orchestrate the forecast pipeline.

        Args:
            request: AleutianLocal forecast request (Pydantic validated)

        Returns:
            AleutianLocal forecast response in expected format

        Raises:
            ValueError: If model family is unknown or unsupported
            httpx.HTTPError: If API calls fail
        """
        logger.info("=" * 80)
        logger.info("🎯 Legacy Forecast Request")
        logger.info(f"   Ticker: {request.name}")
        logger.info(f"   Model: {request.model}")
        logger.info(f"   Context: {request.context_period_size}")
        logger.info(f"   Horizon: {request.forecast_period_size}")
        logger.info("=" * 80)

        # 1. Determine model family
        model_family = determine_model_family(request.model)
        logger.info(f"📊 Model family: {model_family}")

        # 2. Ensure model is initialized
        await self._ensure_model_initialized(model_family, request)

        # 3. Fetch historical data
        prices = await self._fetch_historical_data(
            request.name,
            request.context_period_size
        )

        # 4. Run inference
        forecast = await self._run_inference(
            model_family,
            request,
            prices
        )

        logger.info("=" * 80)
        logger.info("✅ Legacy forecast complete")
        logger.info(f"   Forecast length: {len(forecast.forecast)}")
        logger.info("=" * 80)

        return forecast

    async def _ensure_model_initialized(
        self,
        model_family: str,
        request: AleutianForecastRequest
    ) -> None:
        """
        Check model status and initialize if needed.

        Single responsibility: Model lifecycle management.

        Args:
            model_family: Model family ("chronos", "timesfm", etc.)
            request: Original request (contains model variant info)

        Raises:
            httpx.HTTPError: If status check or initialization fails
        """
        base_path = get_model_base_path(model_family)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Check status
            status_url = f"{self.base_url}{base_path}/status"
            logger.info(f"🔍 Checking model status: {status_url}")

            status_resp = await client.get(
                status_url,
                headers={"Authorization": f"Bearer {settings.API_SECRET_KEY}"}
            )
            status_resp.raise_for_status()
            status_data = status_resp.json()

            model_status = status_data.get("model_status")
            logger.info(f"   Status: {model_status}")

            # Initialize if not ready
            if model_status != "ready":
                logger.info("🔄 Initializing model...")
                init_url = f"{self.base_url}{base_path}/initialization"

                # Build initialization payload (model-specific)
                init_payload = {}
                if model_family == "chronos":
                    init_payload = {"model_variant": request.model}
                # TimesFM and other models may not need variant specification

                init_resp = await client.post(
                    init_url,
                    json=init_payload,
                    headers={"Authorization": f"Bearer {settings.API_SECRET_KEY}"}
                )
                init_resp.raise_for_status()
                logger.info("   ✅ Model initialized")

    async def _fetch_historical_data(
        self,
        ticker: str,
        num_days: int
    ) -> List[float]:
        """
        Fetch historical prices from data service.

        Single responsibility: Data retrieval from InfluxDB via data service.

        Args:
            ticker: Ticker symbol (e.g., "SPY")
            num_days: Number of historical days to fetch

        Returns:
            List of close prices (newest last)

        Raises:
            httpx.HTTPError: If data fetch fails
            ValueError: If response format is invalid
        """
        logger.info(f"📈 Fetching {num_days} days of {ticker} data")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.data_service_url}/v1/data/query",
                json={"ticker": ticker, "days": num_days}
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract close prices from data service response
            # Response format: {"ticker": "SPY", "data": [{"time": "...", "close": 450.2, ...}, ...]}
            if "data" not in data:
                raise ValueError(f"Invalid data response: missing 'data' field")

            prices = [point["close"] for point in data["data"]]
            logger.info(f"   ✅ Fetched {len(prices)} price points")

            return prices

    async def _run_inference(
        self,
        model_family: str,
        request: AleutianForecastRequest,
        prices: List[float]
    ) -> AleutianForecastResponse:
        """
        Run model-specific inference.

        Single responsibility: Route to appropriate model adapter.

        Args:
            model_family: Model family name
            request: Original AleutianLocal request
            prices: Historical close prices

        Returns:
            AleutianLocal forecast response

        Raises:
            ValueError: If model family is unsupported
            httpx.HTTPError: If inference API call fails
        """
        if model_family == "chronos":
            return await self._run_chronos_inference(request, prices)
        elif model_family == "timesfm":
            return await self._run_timesfm_inference(request, prices)
        else:
            raise ValueError(f"Unsupported model family: {model_family}")

    async def _run_chronos_inference(
        self,
        request: AleutianForecastRequest,
        prices: List[float]
    ) -> AleutianForecastResponse:
        """
        Execute Chronos model inference.

        Single responsibility: Chronos-specific API interaction.

        Args:
            request: Original AleutianLocal request
            prices: Historical close prices

        Returns:
            AleutianLocal forecast response (transformed from Chronos format)

        Raises:
            httpx.HTTPError: If Chronos API call fails
        """
        logger.info("🔮 Running Chronos inference")

        # Transform request using pure adapter
        chronos_request = aleutian_to_chronos(request, prices)

        # Call Chronos API
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/forecast/v1/chronos/inference",
                json=chronos_request.model_dump(),
                headers={"Authorization": f"Bearer {settings.API_SECRET_KEY}"}
            )
            resp.raise_for_status()
            chronos_data = resp.json()

        # Parse response
        chronos_response = ChronosInferenceResponse(**chronos_data["prediction"])

        # Transform to AleutianLocal format using pure adapter
        return chronos_to_aleutian(chronos_response, request.name)

    async def _run_timesfm_inference(
        self,
        request: AleutianForecastRequest,
        prices: List[float]
    ) -> AleutianForecastResponse:
        """
        Execute TimesFM model inference.

        Single responsibility: TimesFM-specific service layer interaction.

        This method calls the TimesFM service layer directly instead of using
        the HTTP API, since the API expects CSV files but we have raw arrays.

        Args:
            request: Original AleutianLocal request
            prices: Historical close prices

        Returns:
            AleutianLocal forecast response (transformed from TimesFM format)

        Raises:
            Exception: If TimesFM service call fails
        """
        logger.info("🔮 Running TimesFM inference via service layer")

        # Transform request using pure adapter
        from .legacy_adapters import aleutian_to_timesfm, timesfm_to_aleutian
        from .legacy_schema import TimesFMInferenceResponse
        timesfm_request = aleutian_to_timesfm(request, prices)

        # Call TimesFM service layer directly
        # Import the service module
        from ..models.timesfm20.services import model as timesfm_model_service

        # Run inference (this is synchronous, wrap in async executor)
        import asyncio
        loop = asyncio.get_event_loop()

        results_dict = await loop.run_in_executor(
            None,  # Use default executor
            timesfm_model_service.run_inference,
            timesfm_request.target_inputs,
            timesfm_request.covariates,
            timesfm_request.parameters
        )

        # Parse response into TimesFMInferenceResponse
        timesfm_response = TimesFMInferenceResponse(
            point_forecast=results_dict["point_forecast"],
            quantile_forecast=results_dict.get("quantile_forecast"),
            method=results_dict.get("method", "basic"),
            metadata=results_dict.get("metadata", {})
        )

        # Transform to AleutianLocal format using pure adapter
        return timesfm_to_aleutian(timesfm_response, request.name)
