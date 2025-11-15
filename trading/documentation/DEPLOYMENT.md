# Trading Strategies API - Deployment Guide

Complete deployment guide for the Trading Strategies API.

## Table of Contents

1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [Docker Compose Integration](#docker-compose-integration)
4. [Environment Configuration](#environment-configuration)
5. [Health Checks](#health-checks)
6. [Monitoring and Logging](#monitoring-and-logging)
7. [Troubleshooting](#troubleshooting)

## Local Development

### Prerequisites

- Python 3.11+
- `uv` package manager (installed automatically by `setup.sh`)
- `.env` file with `TRADING_API_KEY` configured

### Setup

```bash
# 1. Initialize trading application
./setup.sh init trading

# 2. Configure environment variables
nano .env
# Set TRADING_API_KEY (min 32 characters)

# 3. Run trading service
./setup.sh run-venv trading
```

### Development Mode

The service runs with auto-reload enabled in development:

```bash
# Service automatically reloads on code changes
./setup.sh run-venv trading
```

### Access Points

- **API**: http://localhost:9000
- **Docs**: http://localhost:9000/docs
- **Health**: http://localhost:9000/health

## Docker Deployment

### Build Docker Image

```bash
docker build -f Dockerfile.trading -t sapheneia-trading .
```

### Run Container

```bash
docker run -d \
  --name sapheneia-trading \
  -p 9000:9000 \
  -e TRADING_API_KEY="your_api_key_min_32_chars" \
  -e TRADING_API_HOST=0.0.0.0 \
  -e TRADING_API_PORT=9000 \
  -e LOG_LEVEL=INFO \
  -e ENVIRONMENT=production \
  sapheneia-trading
```

### Using setup.sh

```bash
# Build and start with Docker Compose
./setup.sh run-docker trading
```

### Container Management

```bash
# View logs
docker logs sapheneia-trading

# Follow logs
docker logs -f sapheneia-trading

# Stop container
docker stop sapheneia-trading

# Remove container
docker rm sapheneia-trading
```

## Docker Compose Integration

The trading service is integrated into `docker-compose.yml`:

```yaml
trading:
  build:
    context: .
    dockerfile: Dockerfile.trading
  container_name: sapheneia-trading
  ports:
    - "${TRADING_API_PORT:-9000}:9000"
  environment:
    - TRADING_API_KEY=${TRADING_API_KEY}
    - TRADING_API_HOST=0.0.0.0
    - TRADING_API_PORT=9000
  volumes:
    - ./trading:/app/trading
    - ./logs:/app/logs
  networks:
    - sapheneia-network
  restart: unless-stopped
```

### Running with Docker Compose

```bash
# Start trading service
docker compose up -d trading

# Start all services (forecast + trading)
docker compose up -d

# View logs
docker compose logs -f trading

# Stop trading service
docker compose stop trading

# Stop all services
docker compose down
```

## Environment Configuration

### Required Variables

```bash
TRADING_API_KEY=your_secure_api_key_minimum_32_characters_long
```

### Optional Variables

```bash
# API Configuration
TRADING_API_HOST=0.0.0.0
TRADING_API_PORT=9000

# Environment
ENVIRONMENT=production  # development, staging, or production
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# CORS Settings
CORS_ALLOWED_ORIGINS=http://localhost:8080,http://localhost:3000
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_EXECUTE_PER_MINUTE=10
```

### Production Requirements

1. **API Key**: Minimum 32 characters, use strong random key
2. **Environment**: Set to `production`
3. **CORS**: Restrict to known origins
4. **Rate Limiting**: Keep enabled
5. **Logging**: Set appropriate `LOG_LEVEL`

## Health Checks

### Health Check Endpoint

```bash
curl http://localhost:9000/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "trading-strategies",
  "version": "1.0.0",
  "available_strategies": ["threshold", "return", "quantile"]
}
```

### Docker Health Check

The Dockerfile includes a health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9000/health || exit 1
```

**Check Status:**
```bash
docker ps  # Shows health status
```

## Monitoring and Logging

### Log Locations

- **Local Development**: Console output
- **Docker**: `docker logs sapheneia-trading`
- **Docker Compose**: `docker compose logs trading`
- **File Logs**: `./logs/` directory (if configured)

### Log Levels

- **DEBUG**: Detailed debugging information
- **INFO**: General information (default)
- **WARNING**: Warning messages
- **ERROR**: Error messages

### Monitoring Endpoints

- **Health**: `GET /health`
- **Status**: `GET /trading/status`
- **Strategies**: `GET /trading/strategies`

### Metrics to Monitor

- Response times
- Error rates
- Rate limit hits
- Capital management events
- Strategy execution counts

## Troubleshooting

### Service Won't Start

**Issue**: Port 9000 already in use

**Solution:**
```bash
# Kill process on port 9000
./setup.sh stop trading

# Or manually
lsof -ti :9000 | xargs kill -9
```

### Docker Build Fails

**Issue**: Build errors

**Solution:**
```bash
# Rebuild from scratch
docker build --no-cache -f Dockerfile.trading -t sapheneia-trading .

# Check Dockerfile syntax
docker build -f Dockerfile.trading .
```

### Container Won't Start

**Issue**: Container exits immediately

**Solution:**
```bash
# Check logs
docker logs sapheneia-trading

# Common issues:
# - Missing TRADING_API_KEY
# - Invalid environment variables
# - Port conflicts
```

### Health Check Fails

**Issue**: Health check returns unhealthy

**Solution:**
```bash
# Check service logs
docker logs sapheneia-trading

# Verify service is running
curl http://localhost:9000/health

# Check container status
docker ps -a
```

### API Key Issues

**Issue**: 401 Unauthorized errors

**Solution:**
```bash
# Verify API key in .env
cat .env | grep TRADING_API_KEY

# Check API key length (min 32 chars in production)
# Regenerate if needed
openssl rand -base64 32
```

### Rate Limiting Issues

**Issue**: 429 Rate Limit Exceeded

**Solution:**
```bash
# Increase rate limits in .env
RATE_LIMIT_EXECUTE_PER_MINUTE=20

# Or disable for development
RATE_LIMIT_ENABLED=false
```

### Performance Issues

**Issue**: Slow response times

**Solution:**
- Check system resources
- Review log levels (DEBUG is slower)
- Check network latency
- Monitor rate limiting impact

## Production Deployment Checklist

- [ ] `TRADING_API_KEY` set (min 32 characters)
- [ ] `ENVIRONMENT=production`
- [ ] CORS origins restricted
- [ ] Rate limiting enabled
- [ ] Health checks configured
- [ ] Logging configured
- [ ] Monitoring set up
- [ ] Backup strategy for API keys
- [ ] Container restart policy set
- [ ] Resource limits configured (if needed)

## Additional Resources

- **API Usage**: [API_USAGE.md](API_USAGE.md)
- **Strategy Guide**: [STRATEGIES.md](STRATEGIES.md)
- **Quick Reference**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Examples**: [EXAMPLES.md](EXAMPLES.md)

