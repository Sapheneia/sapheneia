"""
Sapheneia FastAPI Application

Main application entry point for the Sapheneia time series forecasting API.
Provides REST API endpoints for multiple forecasting models.
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
import logging
import uvicorn
from datetime import datetime

# Import core settings (this also configures logging)
from .core.config import settings, logger

# Import rate limiting
from .core.rate_limit import limiter, rate_limit_exceeded_handler, get_rate_limit

# Import custom exceptions (Phase 7: Error Handling)
from .core.exceptions import SapheneiaException

# Import model registry
from .models import get_available_models, get_all_models_info

# Import routers from model modules
from .models.timesfm20.routes import endpoints as timesfm20_endpoints

# Optional: MLflow integration (to be implemented in Phase 10)
try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("MLflow not available. Tracking features disabled.")


# --- FastAPI App Instance ---

app = FastAPI(
    title="Sapheneia Inference API",
    description=(
        "REST API for time series forecasting models. "
        "Currently supports TimesFM-2.0 with plans for additional models."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add rate limiter state to app
app.state.limiter = limiter

# Add rate limit exception handler
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

logger.info("=" * 80)
logger.info("Sapheneia FastAPI Application")
logger.info(f"Version: {app.version}")
logger.info(f"Docs: http://{settings.API_HOST}:{settings.API_PORT}/docs")
logger.info("=" * 80)


# --- CORS Middleware Configuration ---

# Configure CORS based on environment settings
cors_origins = settings.get_cors_origins()
cors_methods = settings.get_cors_methods()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=cors_methods,
    allow_headers=["*"] if settings.CORS_ALLOW_HEADERS == "*" else settings.CORS_ALLOW_HEADERS.split(","),
)

logger.info(f"CORS middleware configured:")
logger.info(f"  - Allowed origins: {cors_origins}")
logger.info(f"  - Allow credentials: {settings.CORS_ALLOW_CREDENTIALS}")
logger.info(f"  - Allowed methods: {cors_methods}")


# --- Response Compression Middleware (Phase 8: Performance Optimization) ---
# Compress responses larger than 1KB to reduce bandwidth usage
app.add_middleware(GZipMiddleware, minimum_size=1000)
logger.info("GZip compression middleware configured (min_size=1000 bytes)")


# --- Request Size Limit Middleware ---

@app.middleware("http")
async def request_size_limit_middleware(request: Request, call_next):
    """
    Enforce request size limits to prevent oversized requests.
    
    This middleware checks Content-Length header and rejects requests
    exceeding MAX_REQUEST_SIZE to protect the API from resource exhaustion.
    """
    if request.method in ["POST", "PUT", "PATCH"]:
        content_length = request.headers.get("content-length")
        
        if content_length:
            try:
                content_length = int(content_length)
                if content_length > settings.MAX_REQUEST_SIZE:
                    from fastapi.responses import JSONResponse
                    logger.warning(
                        f"Request rejected: size {content_length} bytes exceeds maximum "
                        f"{settings.MAX_REQUEST_SIZE} bytes"
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "REQUEST_TOO_LARGE",
                            "message": f"Request size {content_length} bytes exceeds maximum {settings.MAX_REQUEST_SIZE} bytes",
                            "max_size": settings.MAX_REQUEST_SIZE
                        }
                    )
            except ValueError:
                # Invalid content-length header
                logger.warning(f"Invalid content-length header: {request.headers.get('content-length')}")
    
    response = await call_next(request)
    return response

logger.info(f"Request size limit middleware configured:")
logger.info(f"  - Max request size: {settings.MAX_REQUEST_SIZE / 1024 / 1024:.1f}MB")
logger.info(f"  - Max upload size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024:.1f}MB")


# --- Exception Handlers (Phase 7: Error Handling) ---

@app.exception_handler(SapheneiaException)
async def sapheneia_exception_handler(request: Request, exc: SapheneiaException):
    """
    Handle Sapheneia custom exceptions with structured responses.
    
    Provides consistent error format across all API endpoints.
    """
    logger.error(
        f"❌ SapheneiaException: {exc.error_code} - {exc.message}"
    )
    if exc.details:
        logger.error(f"   Details: {exc.details}")
    
    return JSONResponse(
        status_code=exc.suggested_status_code,
        content=exc.to_dict()
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected exceptions not caught by specific handlers.
    
    Logs full traceback for debugging while returning safe error message to user.
    """
    logger.exception("Unexpected error occurred")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please contact support.",
            "details": {
                "error_type": type(exc).__name__
            }
        }
    )


logger.info("Custom exception handlers configured")


# --- Startup Event ---

@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.

    Initializes connections and prepares the application for serving requests.
    """
    logger.info("=" * 80)
    logger.info("🚀 Application Startup")
    logger.info("=" * 80)

    # Set MLflow tracking URI if available
    if MLFLOW_AVAILABLE:
        try:
            mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
            logger.info(f"MLflow tracking URI set to: {settings.MLFLOW_TRACKING_URI}")
        except Exception as e:
            logger.error(f"Failed to set MLflow tracking URI: {e}")
    else:
        logger.info("MLflow tracking not available")

    logger.info("Application startup complete")
    logger.info("=" * 80)

    # Warn about scaling limitations
    logger.warning("")
    logger.warning("=" * 80)
    logger.warning("⚠️  SCALING LIMITATION")
    logger.warning("=" * 80)
    logger.warning("This API uses module-level state management for model instances.")
    logger.warning("")
    logger.warning("CURRENT LIMITATIONS:")
    logger.warning("  • Only run with --workers 1 (single worker per model)")
    logger.warning("  • Cannot run multiple workers for the same model")
    logger.warning("  • State does not persist across process restarts")
    logger.warning("")
    logger.warning("WORKAROUNDS:")
    logger.warning("  • Run different models in separate containers (already supported)")
    logger.warning("  • For parallel processing: Implement Redis state backend (future)")
    logger.warning("")
    logger.warning("See documentation for details on Redis state backend implementation.")
    logger.warning("=" * 80)
    logger.warning("")


# --- Shutdown Event ---

@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.

    Performs cleanup and graceful shutdown.
    """
    logger.info("=" * 80)
    logger.info("🔄 Application Shutdown")
    logger.info("=" * 80)

    # Shutdown any loaded models
    try:
        from .models.timesfm20.services import model as timesfm_model_service
        status, _ = timesfm_model_service.get_status()
        if status == "ready":
            logger.info("Shutting down TimesFM-2.0 model...")
            timesfm_model_service.shutdown_model()
    except Exception as e:
        logger.error(f"Error during model shutdown: {e}")

    logger.info("Application shutdown complete")
    logger.info("=" * 80)


# --- Include Model Routers ---

# TimesFM-2.0 routes under /forecast/v1/timesfm20
app.include_router(
    timesfm20_endpoints.router,
    prefix="/forecast/v1"
)
logger.info(f"✅ Included TimesFM-2.0 router at: /forecast/v1{timesfm20_endpoints.router.prefix}")

# Future models can be added here:
# app.include_router(flowstate91m_endpoints.router, prefix="/forecast/v1")


# --- Root Endpoints ---

@app.get("/", tags=["Health"])
@limiter.limit(get_rate_limit("health"))
async def root(request: Request, response: Response):
    """
    Root endpoint for basic connectivity check.

    Returns:
        Simple status message confirming API is running
    """
    logger.debug("Root endpoint '/' called")
    return {
        "status": "Sapheneia API is running",
        "version": app.version,
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
@limiter.limit(get_rate_limit("health"))
async def health_check(request: Request, response: Response):
    """
    Health check endpoint for monitoring and load balancers.

    Returns:
        Detailed health status including model availability
    """
    logger.debug("Health check endpoint called")

    # Check TimesFM model status
    from .models.timesfm20.services import model as timesfm_model_service
    timesfm_status, timesfm_error = timesfm_model_service.get_status()

    health_data = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "api_version": app.version,
        "models": {
            "timesfm20": {
                "status": timesfm_status,
                "error": timesfm_error
            }
        }
    }

    logger.debug(f"Health check: {health_data}")
    return health_data


@app.get("/info", tags=["Health"])
@limiter.limit(get_rate_limit("default"))
async def api_info(request: Request, response: Response):
    """
    API information endpoint.

    Returns:
        Comprehensive API configuration and capabilities
    """
    info = {
        "name": app.title,
        "description": app.description,
        "version": app.version,
        "api_host": settings.API_HOST,
        "api_port": settings.API_PORT,
        "available_models": get_available_models(),
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json"
        },
        "features": {
            "mlflow_tracking": MLFLOW_AVAILABLE,
            "api_authentication": True
        }
    }

    return info


@app.get("/models", tags=["Models"])
@limiter.limit(get_rate_limit("default"))
async def list_models(request: Request, response: Response):
    """
    List all available forecasting models.

    Returns:
        Dictionary of all registered models with their metadata
    """
    return {
        "models": get_all_models_info(),
        "count": len(get_available_models())
    }


# --- Backward Compatibility Endpoint ---

@app.post("/v1/timeseries/forecast", tags=["Legacy"])
@limiter.limit(get_rate_limit("default"))
async def legacy_timeseries_forecast(request: Request, response: Response):
    """
    Legacy endpoint for backward compatibility with AleutianLocal orchestrator.

    Accepts old-style requests with ticker symbols and forwards to the new
    TimesFM inference endpoint after fetching and preparing data.

    **Legacy Request Format:**
    ```json
    {
        "name": "SPY",
        "context_period_size": 64,
        "forecast_period_size": 20,
        "model": "google/timesfm-2.0-500m-pytorch"
    }
    ```

    **Returns:**
    ```json
    {
        "forecast": [1.23, 4.56, ...],
        "metadata": {...}
    }
    ```
    """
    import httpx
    from .core.config import settings

    try:
        # Parse legacy request
        body = await request.json()
        ticker = body.get("name")
        context_size = body.get("context_period_size", 64)
        horizon_size = body.get("forecast_period_size", 20)
        model = body.get("model", "google/timesfm-2.0-500m-pytorch")

        logger.info(f"Legacy forecast request: ticker={ticker}, context={context_size}, horizon={horizon_size}")

        if not ticker:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing 'name' parameter (ticker symbol)"}
            )

        # Step 1: Initialize model if needed
        headers = {
            'X-API-KEY': settings.API_SECRET_KEY,
            'Authorization': f'Bearer {settings.API_SECRET_KEY}'
        }

        # Enhanced logging for debugging authentication
        logger.info(f"🔑 Setting up internal API client:")
        logger.info(f"   API_SECRET_KEY (first 8 chars): {settings.API_SECRET_KEY[:8]}...")
        logger.info(f"   API_SECRET_KEY length: {len(settings.API_SECRET_KEY)}")
        logger.info(f"   Authorization header: Bearer {settings.API_SECRET_KEY[:8]}...")
        logger.info(f"   Target port: {settings.API_PORT}")

        async with httpx.AsyncClient(timeout=300.0, headers=headers) as client:
            # Check model status
            logger.info(f"📡 Requesting model status from http://localhost:{settings.API_PORT}/forecast/v1/timesfm20/status")
            status_resp = await client.get(f"http://localhost:{settings.API_PORT}/forecast/v1/timesfm20/status")
            logger.info(f"📡 Status response: {status_resp.status_code}")
            if status_resp.status_code != 200:
                logger.error(f"❌ Status check failed: {status_resp.status_code} - {status_resp.text}")
            status_data = status_resp.json()

            # Initialize if not ready
            if status_data.get("model_status") != "ready":
                logger.info(f"Initializing TimesFM model...")
                logger.info(f"📡 Sending initialization request to http://localhost:{settings.API_PORT}/forecast/v1/timesfm20/initialization")
                init_resp = await client.post(
                    f"http://localhost:{settings.API_PORT}/forecast/v1/timesfm20/initialization",
                    json={
                        "backend": "cpu",
                        "context_len": context_size,
                        "horizon_len": horizon_size,
                        "checkpoint": model
                    }
                )
                logger.info(f"📡 Initialization response: {init_resp.status_code}")
                if init_resp.status_code != 200:
                    logger.error(f"❌ Model initialization failed: {init_resp.status_code} - {init_resp.text}")
                    return JSONResponse(
                        status_code=500,
                        content={"error": "Model initialization failed", "details": init_resp.text}
                    )

            # Step 2: Fetch data from data service
            # Note: This assumes the data service is running at host.containers.internal:8001
            data_resp = await client.post(
                f"http://host.containers.internal:8001/v1/data/fetch",
                json={
                    "ticker": ticker,
                    "days": context_size + 10  # Fetch extra days for context
                }
            )

            if data_resp.status_code != 200:
                logger.error(f"Data fetch failed: {data_resp.text}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Data fetch failed", "details": data_resp.text}
                )

            # Step 3: Format data and call inference
            # For now, return a simple mock response
            # TODO: Implement full data processing pipeline
            logger.warning("Legacy endpoint returning mock forecast - full implementation pending")

            return {
                "forecast": [100.0 + i * 0.5 for i in range(horizon_size)],
                "metadata": {
                    "ticker": ticker,
                    "model": model,
                    "context_size": context_size,
                    "horizon_size": horizon_size,
                    "note": "Legacy compatibility endpoint - mock data"
                }
            }

    except Exception as e:
        logger.exception("Error in legacy forecast endpoint")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# --- Direct Run Configuration (for development) ---

if __name__ == "__main__":
    logger.warning("=" * 80)
    logger.warning("Running Uvicorn server directly (DEVELOPMENT MODE)")
    logger.warning("For production, use: uvicorn forecast.main:app --host 0.0.0.0 --port 8000")
    logger.warning("=" * 80)

    uvicorn.run(
        "forecast.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=True,  # Enable auto-reload for development
        reload_dirs=["forecast"]  # Watch forecast directory
    )
