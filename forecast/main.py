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
