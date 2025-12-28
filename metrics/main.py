"""
Sapheneia Metrics API

FastAPI service for calculating financial performance metrics.
Provides REST endpoints for Sharpe ratio, maximum drawdown, CAGR,
Calmar ratio, and win rate calculations.

Built on top of quantstats library for robust, industry-standard metrics.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from metrics.core.config import settings
from metrics.routes import endpoints

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Sapheneia Metrics API",
    description="Financial performance metrics calculation service for trading strategies",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(endpoints.router, prefix="/metrics/v1")


@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "service": "Sapheneia Metrics API",
        "version": "2.0.0",
        "status": "operational",
        "description": "Financial performance metrics calculation service",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "compute": "/metrics/v1/compute"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "metrics",
        "version": "2.0.0"
    }


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Starting Sapheneia Metrics API v2.0.0")
    logger.info(f"API running on {settings.HOST}:{settings.PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("Shutting down Sapheneia Metrics API")
