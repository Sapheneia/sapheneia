# Forecast Application - Deployment Guide

Complete deployment guide for the Forecast Application.

## Table of Contents

1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [Docker Compose Integration](#docker-compose-integration)
4. [Environment Configuration](#environment-configuration)
5. [Health Checks](#health-checks)
6. [Monitoring and Logging](#monitoring-and-logging)
7. [Troubleshooting](#troubleshooting)
8. [Production Deployment](#production-deployment)
9. [Scaling Considerations](#scaling-considerations)

## Local Development

### Prerequisites

- Python 3.11+
- `uv` package manager (installed automatically by `setup.sh`)
- `.env` file with `API_SECRET_KEY` configured

### Setup

```bash
# 1. Initialize forecast application
./setup.sh init forecast

# 2. Configure environment variables
nano .env
# Set API_SECRET_KEY (change from default!)

# 3. Run forecast API
./setup.sh run-venv forecast api

# 4. (Optional) Run UI application
./setup.sh run-venv forecast ui

# 5. (Optional) Run both API and UI
./setup.sh run-venv forecast all
```

### Development Mode

The service runs with auto-reload enabled in development:

```bash
# Service automatically reloads on code changes
./setup.sh run-venv forecast api
```

### Access Points

- **API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **API Docs (ReDoc)**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **UI**: http://localhost:8080 (if running)

### Stopping Services

```bash
# Stop forecast services
./setup.sh stop forecast
```

## Docker Deployment

### Prerequisites

- Docker installed and running
- Docker Compose (optional, for multi-service deployment)

### Build Docker Image

```bash
# Build forecast API image
docker build -f Dockerfile.forecast -t sapheneia-forecast .

# Or using setup.sh
./setup.sh run-docker forecast api
```

### Run Container

```bash
# Run forecast API container
docker run -d \
  --name sapheneia-forecast \
  -p 8000:8000 \
  -e API_SECRET_KEY=your_secret_key \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/forecast/models/timesfm20/local:/app/forecast/models/timesfm20/local \
  sapheneia-forecast

# Or using setup.sh
./setup.sh run-docker forecast api
```

### View Logs

```bash
# View container logs
docker logs -f sapheneia-forecast

# Or using docker-compose
docker-compose logs -f forecast
```

### Stop Container

```bash
# Stop container
docker stop sapheneia-forecast
docker rm sapheneia-forecast

# Or using setup.sh
./setup.sh stop forecast
```

## Docker Compose Integration

### Overview

Docker Compose orchestrates multiple services:
- `forecast`: Forecast API service
- `ui`: UI application (depends on forecast)

### Start Services

```bash
# Start all services
./setup.sh run-docker forecast all

# Or using docker-compose directly
docker-compose up -d
```

### Start Individual Services

```bash
# Start only forecast API
./setup.sh run-docker forecast api

# Start only UI
./setup.sh run-docker forecast ui
```

### View Logs

```bash
# All services
docker-compose logs -f

# Forecast API only
docker-compose logs -f forecast

# UI only
docker-compose logs -f ui
```

### Stop Services

```bash
# Stop all services
./setup.sh stop forecast

# Or using docker-compose
docker-compose down
```

### Rebuild Images

```bash
# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Environment Configuration

### Required Variables

**Forecast Application:**
```bash
API_SECRET_KEY=your_secret_key_change_me_in_production  # CHANGE THIS!
```

### Optional Variables

**API Settings:**
```bash
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
ENVIRONMENT=development  # development, staging, or production
```

**CORS Settings:**
```bash
CORS_ALLOWED_ORIGINS=http://localhost:8080,http://localhost:3000
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_ALLOW_HEADERS=*
```

**Rate Limiting:**
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_INFERENCE_PER_MINUTE=10
RATE_LIMIT_STORAGE_URI=memory://  # Use redis://localhost:6379 for distributed
```

**Request Size Limits:**
```bash
MAX_REQUEST_SIZE=10485760  # 10MB in bytes
MAX_UPLOAD_SIZE=52428800   # 50MB in bytes
```

**TimesFM-2.0 Defaults:**
```bash
TIMESFM20_DEFAULT_BACKEND=cpu
TIMESFM20_DEFAULT_CONTEXT_LEN=64
TIMESFM20_DEFAULT_HORIZON_LEN=24
TIMESFM20_DEFAULT_CHECKPOINT=google/timesfm-2.0-500m-pytorch
```

**MLOps (Optional):**
```bash
MLFLOW_TRACKING_URI=http://localhost:5000
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

**UI Settings:**
```bash
UI_API_BASE_URL=http://localhost:8000
UI_PORT=8080
```

### Environment File Setup

1. Copy template:
```bash
cp .env.template .env
```

2. Edit `.env` file:
```bash
nano .env
```

3. Set required variables (especially `API_SECRET_KEY`)

4. Restart services to apply changes

## Health Checks

### Health Check Endpoint

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-13T12:00:00",
  "api_version": "2.0.0",
  "models": {
    "timesfm20": {
      "status": "ready",
      "error": null
    }
  }
}
```

### Health Check Status Values

- `healthy`: API is operational
- `unhealthy`: API has issues (check model status)

### Model Status Values

- `uninitialized`: Model not loaded
- `initializing`: Model is loading
- `ready`: Model ready for inference
- `error`: Model encountered an error

### Docker Health Checks

Docker Compose includes health checks:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Monitoring Integration

Health check endpoint can be integrated with:
- Kubernetes liveness/readiness probes
- Load balancer health checks
- Monitoring systems (Prometheus, Datadog, etc.)

## Monitoring and Logging

### Logging Configuration

Logs are written to:
- **Console**: Standard output (Docker captures this)
- **File**: `logs/forecast.log` (if configured)

### Log Levels

- `DEBUG`: Detailed debugging information
- `INFO`: General informational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical errors

### Viewing Logs

**Virtual Environment:**
```bash
# View log file
tail -f logs/forecast.log
```

**Docker:**
```bash
# View container logs
docker logs -f sapheneia-forecast

# View last 100 lines
docker logs --tail 100 sapheneia-forecast

# View logs with timestamps
docker logs -f -t sapheneia-forecast
```

**Docker Compose:**
```bash
# All services
docker-compose logs -f

# Forecast API only
docker-compose logs -f forecast

# Follow logs with timestamps
docker-compose logs -f -t forecast
```

### Performance Monitoring

The API includes performance monitoring middleware:
- `X-Process-Time` header: Request processing time in seconds
- `X-Request-ID` header: Unique request identifier

### Metrics to Monitor

- **Request Rate**: Requests per second
- **Response Times**: Average, p50, p95, p99
- **Error Rate**: Percentage of failed requests
- **Model Status**: Model initialization and inference status
- **Memory Usage**: Container memory usage
- **CPU Usage**: Container CPU usage

## Troubleshooting

### API Won't Start

**Symptoms:**
- Port already in use
- Import errors
- Configuration errors

**Solutions:**
```bash
# Check if port is in use
lsof -i :8000

# Kill process if needed
lsof -ti :8000 | xargs kill -9

# Check logs
tail -f logs/forecast.log

# Verify environment
cat .env

# Check Python version
python --version  # Should be 3.11+

# Reinstall dependencies
./setup.sh init forecast
```

### Authentication Errors

**Symptoms:**
```json
{"detail": "Not authenticated"}
```

**Solutions:**
- Verify `API_SECRET_KEY` in `.env` matches request header
- Check header format: `Authorization: Bearer YOUR_KEY`
- Ensure no extra spaces in header
- Try in Swagger UI first: http://localhost:8000/docs

### Model Initialization Fails

**Symptoms:**
- Out of memory errors
- Slow initialization
- Download failures

**Solutions:**
- Ensure sufficient RAM (4GB+ for TimesFM-2.0)
- Verify internet connection (HuggingFace downloads)
- Check disk space (3.8GB for TimesFM weights)
- Review logs: `docker-compose logs forecast`
- Try different backend: `"backend": "cpu"` or `"backend": "gpu"`

### Data Source Errors

**Symptoms:**
```json
{"detail": "Data error: Local file not found: /app/data/uploads/file.csv"}
```

**Solutions:**

**Venv mode** - Use relative paths:
```json
{
  "data_source_url_or_path": "data/uploads/file.csv"
}
```

**Docker mode** - Use absolute paths:
```json
{
  "data_source_url_or_path": "/app/data/uploads/file.csv"
}
```

### Docker Issues

**Rebuild from scratch:**
```bash
./setup.sh stop forecast
docker-compose down -v
docker-compose build --no-cache
./setup.sh run-docker forecast all
```

**Check container status:**
```bash
docker ps -a
```

**View logs:**
```bash
docker-compose logs -f forecast
```

**Check resources:**
```bash
docker stats
```

**Docker won't stop:**
```bash
# Manual stop
docker stop sapheneia-forecast sapheneia-ui
docker rm sapheneia-forecast sapheneia-ui

# Or use Docker Desktop GUI
```

### Performance Issues

**Symptoms:**
- Slow inference
- High memory usage
- Timeout errors

**Solutions:**
- Check model status: `curl http://localhost:8000/forecast/v1/timesfm20/status`
- Monitor resource usage: `docker stats`
- Reduce `context_len` if using large values
- Check for memory leaks in logs
- Consider using GPU backend if available

## Production Deployment

### Production Checklist

- [ ] Change `API_SECRET_KEY` from default
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure HTTPS (reverse proxy)
- [ ] Set appropriate CORS origins
- [ ] Configure rate limiting
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation
- [ ] Set up health check monitoring
- [ ] Configure backup strategy
- [ ] Review security settings

### Reverse Proxy Configuration

**Nginx Example:**
```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### HTTPS Configuration

Use a reverse proxy (Nginx, Traefik) with SSL certificates (Let's Encrypt, etc.)

### Resource Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 4GB
- Disk: 10GB (includes model weights)

**Recommended:**
- CPU: 4+ cores
- RAM: 8GB+
- Disk: 20GB+
- GPU: Optional (for faster inference)

### High Availability

For high availability:
- Deploy multiple instances behind load balancer
- Use Redis for distributed state (future)
- Implement health check monitoring
- Set up automatic failover

## Scaling Considerations

### Current Limitations

⚠️ **IMPORTANT**: The current implementation uses module-level state management:

- **Single Worker Only**: Must run with `--workers 1`
- **No Horizontal Scaling**: Cannot run multiple instances of same model
- **State Non-Persistent**: State lost on restart

### Scaling Options

**1. Multiple Different Models:**
- Run different models in separate containers
- Each model has isolated state
- ✅ Supported

**2. Single Model, Multiple Instances:**
- Requires Redis state backend (future)
- Enables horizontal scaling
- ❌ Not yet supported

**3. Vertical Scaling:**
- Increase container resources (CPU, RAM)
- Use GPU backend for faster inference
- ✅ Supported

### Future: Redis State Backend

For production scaling:
- Implement Redis state backend
- Enable multiple workers per model
- Enable horizontal scaling
- Enable state persistence

See [Architecture Documentation](ARCHITECTURE.md#state-management) for details.

---

**See also:**
- [Architecture Documentation](ARCHITECTURE.md) - System architecture
- [API Usage Guide](API_USAGE.md) - API usage instructions
- [Quick Reference](QUICK_REFERENCE.md) - Quick reference card

