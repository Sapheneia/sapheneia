"""
Sapheneia FastAPI Application

Main application entry point for the Sapheneia time series forecasting API.
Provides REST API endpoints for multiple forecasting models.
"""

from datetime import datetime

import uvicorn
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

# Import shared error handlers for orchestration code running in this process
from shared.errors import register_error_handlers

# Import core settings (this also configures logging)
from .core.config import logger, settings

# Import custom exceptions (Phase 7: Error Handling)
from .core.exceptions import SapheneiaException

# Import rate limiting
from .core.rate_limit import get_rate_limit, limiter, rate_limit_exceeded_handler

# Import authentication
from .core.security import get_api_key

# Import model registry
from .models import get_all_models_info, get_available_models
from .models.chronos.routes import endpoints as chronos_endpoints

# Import routers from model modules
from .models.timesfm20.routes import endpoints as timesfm20_endpoints

# Forecast service is stateless beyond the singleton model state inside the
# per-model containers. Run-state ownership lives in the orchestrator service
# now; this process no longer hosts an orchestration HTTP surface.


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
    openapi_url="/openapi.json",
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
    allow_headers=(
        ["*"] if settings.CORS_ALLOW_HEADERS == "*" else settings.CORS_ALLOW_HEADERS.split(",")
    ),
)

logger.info("CORS middleware configured:")
logger.info(f"  - Allowed origins: {cors_origins}")
logger.info(f"  - Allow credentials: {settings.CORS_ALLOW_CREDENTIALS}")
logger.info(f"  - Allowed methods: {cors_methods}")


# --- Response Compression Middleware (Phase 8: Performance Optimization) ---
# Compress responses larger than 1KB to reduce bandwidth usage
app.add_middleware(GZipMiddleware, minimum_size=1000)
logger.info("GZip compression middleware configured (min_size=1000 bytes)")


# --- Request-ID Middleware ---
# Mirrors trading/main.py: every request gets an X-Request-ID (generated if
# the caller didn't supply one) so logs can be correlated across services.
import uuid as _uuid  # noqa: E402


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or _uuid.uuid4().hex
    request.state.request_id = rid
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


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
                            "max_size": settings.MAX_REQUEST_SIZE,
                        },
                    )
            except ValueError:
                # Invalid content-length header
                logger.warning(
                    f"Invalid content-length header: {request.headers.get('content-length')}"
                )

    response = await call_next(request)
    return response


logger.info("Request size limit middleware configured:")
logger.info(f"  - Max request size: {settings.MAX_REQUEST_SIZE / 1024 / 1024:.1f}MB")
logger.info(f"  - Max upload size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024:.1f}MB")


# --- Exception Handlers (Phase 7: Error Handling) ---


@app.exception_handler(SapheneiaException)
async def sapheneia_exception_handler(request: Request, exc: SapheneiaException):
    """
    Handle Sapheneia custom exceptions with structured responses.

    Provides consistent error format across all API endpoints.
    """
    logger.error(f"❌ SapheneiaException: {exc.error_code} - {exc.message}")
    if exc.details:
        logger.error(f"   Details: {exc.details}")

    return JSONResponse(status_code=exc.suggested_status_code, content=exc.to_dict())


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
            "details": {"error_type": type(exc).__name__},
        },
    )


# Register shared SapheneiaError handlers (for orchestration code running in this process)
register_error_handlers(app)
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

    # Hard-fail if running with multiple workers — the per-family model
    # singletons would corrupt under concurrent process workers.
    import os as _os

    workers = int(_os.getenv("UVICORN_WORKERS", "1") or "1")
    if workers != 1:
        raise RuntimeError(
            f"forecast service requires UVICORN_WORKERS=1 (got {workers}); "
            "use container-per-model sharding for parallelism"
        )

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

    # Shutdown any loaded models (TimesFM and Chronos)
    try:
        from .models.timesfm20.services import model as timesfm_model_service

        status, _ = timesfm_model_service.get_status()
        if status == "ready":
            logger.info("Shutting down TimesFM-2.0 model...")
            timesfm_model_service.shutdown_model()
    except Exception as e:
        logger.error(f"Error during TimesFM model shutdown: {e}")

    try:
        from .models.chronos.services import model as chronos_model_service

        c_status, _ = chronos_model_service.get_status()
        if c_status == "ready":
            logger.info("Shutting down Chronos model...")
            chronos_model_service.shutdown_model()
    except Exception as e:
        logger.error(f"Error during Chronos model shutdown: {e}")

    logger.info("Application shutdown complete")
    logger.info("=" * 80)


# --- Include Model Routers ---

# TimesFM-2.0 routes under /forecast/v1/timesfm20
app.include_router(timesfm20_endpoints.router, prefix="/forecast/v1")
logger.info(f"✅ Included TimesFM-2.0 router at: /forecast/v1{timesfm20_endpoints.router.prefix}")

# Chronos routes under /forecast/v1/chronos
app.include_router(chronos_endpoints.router, prefix="/forecast/v1")
logger.info(f"✅ Included Chronos router at: /forecast/v1{chronos_endpoints.router.prefix}")

# Generic inference endpoint at /forecast/v1/inference for dedicated model containers.
# When a container runs a single model (e.g., chronos-t5-tiny), it exposes inference
# at the generic path without the model name prefix. This allows the orchestration
# service to call a consistent endpoint regardless of which model container is targeted.
from fastapi import APIRouter, Body  # noqa: E402

from .models.chronos.routes.endpoints import (  # noqa: E402
    inference_endpoint as chronos_inference_endpoint,
)
from .models.chronos.schemas.schema import InferenceInput, InferenceOutput  # noqa: E402

generic_inference_router = APIRouter(
    tags=["Generic Inference"], dependencies=[Depends(get_api_key)]
)


@generic_inference_router.post("/inference", response_model=InferenceOutput)
@limiter.limit(get_rate_limit("inference"))
async def generic_inference_endpoint(
    request: Request, response: Response, input_data: InferenceInput = Body()
):
    """
    Generic inference endpoint for dedicated model containers.

    This endpoint provides a model-agnostic path for inference requests.
    It delegates to the active model's inference implementation (currently Chronos).

    Use this endpoint when calling dedicated model containers that run a single model.
    """
    return await chronos_inference_endpoint(request, response, input_data)


app.include_router(generic_inference_router, prefix="/forecast/v1")
logger.info("✅ Included generic inference router at: /forecast/v1/inference")

# Future models can be added here:
# app.include_router(other_model_endpoints.router, prefix="/forecast/v1")


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
        "docs": "/docs",
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
        "models": {"timesfm20": {"status": timesfm_status, "error": timesfm_error}},
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
            "openapi_json": "/openapi.json",
        },
        "features": {"api_authentication": True},
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
    return {"models": get_all_models_info(), "count": len(get_available_models())}


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
        reload_dirs=["forecast"],  # Watch forecast directory
    )
