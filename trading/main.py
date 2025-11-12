"""
Trading Strategies FastAPI Application

Main entry point for the trading strategies service.
Provides REST API endpoints for executing trading strategies.
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
import uvicorn

# Import core settings (this also configures logging)
from .core.config import settings, logger

# Import rate limiting
from .core.rate_limit import limiter, rate_limit_exceeded_handler, get_rate_limit

# Import custom exceptions
from .core.exceptions import TradingException

# Import routers
from .routes import endpoints

# --- FastAPI App Instance ---

app = FastAPI(
    title="Sapheneia Trading Strategies API",
    description=(
        "Trading strategy execution service for long-only positions. "
        "Supports threshold, return, and quantile-based strategies."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add rate limiter state to app
app.state.limiter = limiter

# Add rate limit exception handler
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

logger.info("=" * 80)
logger.info("Sapheneia Trading Strategies API")
logger.info(f"Version: {app.version}")
logger.info(
    f"Docs: http://{settings.TRADING_API_HOST}:{settings.TRADING_API_PORT}/docs"
)
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
        ["*"]
        if settings.CORS_ALLOW_HEADERS == "*"
        else settings.CORS_ALLOW_HEADERS.split(",")
    ),
)

logger.info("CORS middleware configured:")
logger.info(f"  - Allowed origins: {cors_origins}")
logger.info(f"  - Allow credentials: {settings.CORS_ALLOW_CREDENTIALS}")
logger.info(f"  - Allowed methods: {cors_methods}")


# --- Response Compression Middleware ---
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
                # Default max size: 10MB (can be configured in settings if needed)
                max_size = 10 * 1024 * 1024  # 10MB
                if content_length > max_size:
                    logger.warning(
                        f"Request rejected: size {content_length} bytes exceeds maximum "
                        f"{max_size} bytes"
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "REQUEST_TOO_LARGE",
                            "message": (
                                f"Request size {content_length} bytes "
                                f"exceeds maximum {max_size} bytes"
                            ),
                            "max_size": max_size,
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
logger.info("  - Max request size: 10MB")


# --- Exception Handlers ---


@app.exception_handler(TradingException)
async def trading_exception_handler(
    request: Request, exc: TradingException
) -> JSONResponse:
    """
    Handle TradingException and convert to HTTP response.

    Provides consistent error format across all API endpoints.
    Note: Router-level handlers may also catch these, but this provides global fallback.
    """
    logger.error(f"TradingException: {exc.error_code} - {exc.message}")
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


logger.info("Custom exception handlers configured")


# --- Include Routers ---

# Trading routes under /trading (NOT /api - that's reserved for models application)
app.include_router(
    endpoints.router,
    # Router already has prefix="/trading" defined, so no additional prefix needed
)
logger.info(f"✅ Included Trading Strategies router at: {endpoints.router.prefix}")


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
        "status": "ok",
        "service": "trading-strategies",
        "version": app.version,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
@limiter.limit(get_rate_limit("health"))
async def health_check(request: Request, response: Response):
    """
    Health check endpoint for monitoring and load balancers.

    Returns:
        Detailed health status including available strategies
    """
    logger.debug("Health check endpoint called")

    return {
        "status": "healthy",
        "service": "trading-strategies",
        "version": app.version,
        "available_strategies": ["threshold", "return", "quantile"],
    }


# --- Startup Event ---


@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.

    Initializes connections and prepares the application for serving requests.
    """
    logger.info("=" * 80)
    logger.info("🚀 Trading Strategies API Startup")
    logger.info("=" * 80)
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(
        f"API Host:Port: {settings.TRADING_API_HOST}:{settings.TRADING_API_PORT}"
    )
    logger.info(
        f"Rate limiting: {'enabled' if settings.RATE_LIMIT_ENABLED else 'disabled'}"
    )
    logger.info(
        f"Execute endpoint limit: {settings.RATE_LIMIT_EXECUTE_PER_MINUTE}/minute"
    )
    logger.info("Available strategies: threshold, return, quantile")
    logger.info("Application startup complete")
    logger.info("=" * 80)


# --- Shutdown Event ---


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.

    Performs cleanup and graceful shutdown.
    """
    logger.info("=" * 80)
    logger.info("🔄 Trading Strategies API Shutdown")
    logger.info("=" * 80)
    logger.info("Application shutdown complete")
    logger.info("=" * 80)


# --- Direct Run Configuration (for development) ---

if __name__ == "__main__":
    logger.warning("=" * 80)
    logger.warning("Running Uvicorn server directly (DEVELOPMENT MODE)")
    logger.warning(
        "For production, use: uvicorn trading.main:app --host 0.0.0.0 --port 9000"
    )
    logger.warning("=" * 80)

    uvicorn.run(
        "trading.main:app",
        host=settings.TRADING_API_HOST,
        port=settings.TRADING_API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=True,  # Enable auto-reload for development
        reload_dirs=["trading"],  # Watch trading directory
    )
