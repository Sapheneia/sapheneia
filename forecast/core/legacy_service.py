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
        """
        Initialize service with API endpoints.

        ARCHITECTURE NOTE: This service does NOT connect to databases.
        It's a pure inference engine that receives data from the orchestrator.
        """
        self.base_url = f"http://localhost:{settings.API_PORT}"
        self.timeout = 300.0  # 5 minutes for model operations

    async def forecast(
        self,
        request: AleutianForecastRequest
    ) -> AleutianForecastResponse:
        """
        Process forecast request from AleutianLocal.

        Single responsibility: Orchestrate the forecast pipeline.

        CRITICAL UPDATE (2025-12-22): Implements priority logic for data source:
        1. If `recent_data` is provided → Use it directly (backtest mode)
        2. Otherwise → Query database (live mode)

        Args:
            request: AleutianLocal forecast request (Pydantic validated)

        Returns:
            AleutianLocal forecast response in expected format

        Raises:
            ValueError: If model family is unknown or unsupported
            httpx.HTTPError: If API calls fail
        """
        logger.info("=" * 80)
        logger.info("🎯 LEGACY FORECAST REQUEST RECEIVED")
        logger.info("=" * 80)
        logger.info(f"📋 REQUEST DETAILS:")
        logger.info(f"   Ticker: {request.name}")
        logger.info(f"   Model: {request.model}")
        logger.info(f"   Context Period Size: {request.context_period_size}")
        logger.info(f"   Forecast Period Size: {request.forecast_period_size}")
        logger.info(f"   As-Of Date: {request.as_of_date if request.as_of_date else 'NOT PROVIDED'}")

        # CRITICAL: Log received data (recent_data is now REQUIRED)
        logger.info("=" * 80)
        logger.info("🔍 DATA VALIDATION:")
        logger.info(f"   ✅ recent_data RECEIVED FROM ORCHESTRATOR")
        logger.info(f"   🔒 Python service operates in PURE INFERENCE mode")
        logger.info(f"   🔒 NO database queries - orchestrator is data source")
        logger.info(f"   recent_data Length: {len(request.recent_data)}")
        logger.info(f"   recent_data First 5 values: {request.recent_data[:5]}")
        logger.info(f"   recent_data Last 5 values: {request.recent_data[-5:]}")
        logger.info(f"   recent_data Min: {min(request.recent_data):.2f}")
        logger.info(f"   recent_data Max: {max(request.recent_data):.2f}")
        logger.info(f"   recent_data Mean: {sum(request.recent_data)/len(request.recent_data):.2f}")
        logger.info("=" * 80)

        # 1. Determine model family
        model_family = determine_model_family(request.model)
        logger.info(f"📊 Model family: {model_family}")

        # 2. Ensure model is initialized
        await self._ensure_model_initialized(model_family, request)

        # 3. Fetch historical data (PRIORITY LOGIC)
        prices = await self._fetch_historical_data(
            request.name,
            request.context_period_size,
            recent_data=request.recent_data,
            as_of_date=request.as_of_date
        )

        # Log the prices that will be passed to the model
        logger.info("=" * 80)
        logger.info("📊 PRICES READY FOR MODEL INFERENCE:")
        logger.info("=" * 80)
        logger.info(f"   Total Price Points: {len(prices)}")
        logger.info(f"   First 10: {prices[:10]}")
        logger.info(f"   Last 10: {prices[-10:]}")
        logger.info(f"   Min: {min(prices):.2f}, Max: {max(prices):.2f}, Mean: {sum(prices)/len(prices):.2f}")
        logger.info("=" * 80)

        # 4. Run inference
        forecast = await self._run_inference(
            model_family,
            request,
            prices
        )

        logger.info("=" * 80)
        logger.info("✅ LEGACY FORECAST COMPLETE")
        logger.info("=" * 80)
        logger.info(f"📊 FINAL OUTPUT:")
        logger.info(f"   Ticker: {forecast.name}")
        logger.info(f"   Forecast Values: {forecast.forecast}")
        logger.info(f"   Forecast Length: {len(forecast.forecast)}")
        logger.info(f"   Message: {forecast.message}")
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
        num_days: int,
        recent_data: List[float],  # NOW REQUIRED!
        as_of_date: Optional[str] = None
    ) -> List[float]:
        """
        Process historical data from orchestrator.

        CRITICAL ARCHITECTURE DECISION (2025-12-22):
        Python service is a PURE INFERENCE ENGINE - it does NOT query databases.
        All data MUST come from the Go orchestrator.

        Single responsibility: Validate and return data from orchestrator.

        Args:
            ticker: Ticker symbol (for logging only)
            num_days: Expected context size (for validation)
            recent_data: Historical prices from orchestrator (REQUIRED)
            as_of_date: ISO date string (for logging/metadata only)

        Returns:
            List of close prices (newest last)

        Raises:
            ValueError: If data validation fails
        """
        logger.info("=" * 80)
        logger.info("✅ USING DATA FROM ORCHESTRATOR (PURE INFERENCE MODE)")
        logger.info("=" * 80)
        logger.info(f"📊 Processing recent_data from orchestrator")
        logger.info(f"   Ticker: {ticker}")
        logger.info(f"   As-Of Date: {as_of_date if as_of_date else 'N/A (live mode)'}")
        logger.info(f"   Data Length: {len(recent_data)}")
        logger.info(f"   Expected context_period_size: {num_days}")

        # Validation: Check data length against expected context size
        if len(recent_data) < num_days:
            logger.warning("=" * 80)
            logger.warning("⚠️ WARNING: DATA LENGTH MISMATCH")
            logger.warning(f"   Provided: {len(recent_data)} points")
            logger.warning(f"   Expected: {num_days} points")
            logger.warning(f"   Will use all {len(recent_data)} available points")
            logger.warning("=" * 80)

        # Log detailed statistics about the data
        logger.info(f"📈 DATA STATISTICS:")
        logger.info(f"   First 10 values: {recent_data[:10]}")
        logger.info(f"   Last 10 values: {recent_data[-10:]}")
        logger.info(f"   Min price: {min(recent_data):.2f}")
        logger.info(f"   Max price: {max(recent_data):.2f}")
        logger.info(f"   Mean price: {sum(recent_data)/len(recent_data):.2f}")
        logger.info(f"   Range: {max(recent_data) - min(recent_data):.2f}")

        # Return the data as-is (orchestrator has already sliced it correctly)
        logger.info(f"✅ VALIDATED AND RETURNING {len(recent_data)} price points")
        logger.info(f"   🔒 Python service NEVER queries database - data from orchestrator only")
        logger.info("=" * 80)

        return recent_data

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
        logger.info("=" * 80)
        logger.info("🔮 RUNNING CHRONOS MODEL INFERENCE")
        logger.info("=" * 80)

        # Transform request using pure adapter
        chronos_request = aleutian_to_chronos(request, prices)

        logger.info(f"📤 CHRONOS REQUEST PAYLOAD:")
        logger.info(f"   Context Length: {len(chronos_request.context)}")
        logger.info(f"   Context First 10: {chronos_request.context[:10]}")
        logger.info(f"   Context Last 10: {chronos_request.context[-10:]}")
        logger.info(f"   Context Min: {min(chronos_request.context):.2f}")
        logger.info(f"   Context Max: {max(chronos_request.context):.2f}")
        logger.info(f"   Context Mean: {sum(chronos_request.context)/len(chronos_request.context):.2f}")
        logger.info(f"   Prediction Length: {chronos_request.prediction_length}")
        logger.info(f"   Num Samples: {chronos_request.num_samples}")
        logger.info("=" * 80)

        # Call Chronos API
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(f"📡 Calling Chronos API:")
            logger.info(f"   URL: {self.base_url}/forecast/v1/chronos/inference")

            resp = await client.post(
                f"{self.base_url}/forecast/v1/chronos/inference",
                json=chronos_request.model_dump(),
                headers={"Authorization": f"Bearer {settings.API_SECRET_KEY}"}
            )
            resp.raise_for_status()
            chronos_data = resp.json()

            logger.info(f"📥 CHRONOS RESPONSE RECEIVED:")
            logger.info(f"   Status Code: {resp.status_code}")
            logger.info(f"   Response Keys: {list(chronos_data.keys())}")

        # Parse response
        chronos_response = ChronosInferenceResponse(**chronos_data["prediction"])

        logger.info(f"📊 CHRONOS FORECAST OUTPUT:")
        logger.info(f"   Median Forecast: {chronos_response.median}")
        logger.info(f"   Mean Forecast: {chronos_response.mean}")
        logger.info(f"   Forecast Length: {len(chronos_response.median)}")
        logger.info("=" * 80)

        # Transform to AleutianLocal format using pure adapter
        aleutian_response = chronos_to_aleutian(chronos_response, request.name)

        logger.info(f"📤 FINAL RESPONSE TO ALEUTIAN:")
        logger.info(f"   Ticker: {aleutian_response.name}")
        logger.info(f"   Forecast: {aleutian_response.forecast}")
        logger.info(f"   Message: {aleutian_response.message}")
        logger.info("=" * 80)

        return aleutian_response

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
