# Local Development Setup Guide

This guide walks new contributors through setting up a local development environment for Sapheneia.

---

## Prerequisites

Ensure the following are installed before proceeding:

- **Python 3.11+**
- **Go 1.21+** (required for the data service)
- **Docker or Podman** with Compose support
- **InfluxDB 2.x** (runs on the `aleutian-shared` Docker network, port `12130`)
- **Git**

---

## Setup Steps

### 1. Clone the Repository

```bash
git clone <repo-url>
cd sapheneia
```

### 2. Configure Environment Variables

```bash
cp .env.template .env
# Edit .env with your values
```

Open `.env` in your editor and fill in the required values. The key variables are described in the next section.

### 3. Key Environment Variables

| Variable | Description |
|---|---|
| `API_SECRET_KEY` | API authentication key for the orchestration gateway |
| `TRADING_API_KEY` | Authentication key for the trading service |
| `INFLUXDB_URL` | InfluxDB connection URL — must match the Aleutian setup |
| `INFLUXDB_TOKEN` | InfluxDB authentication token |
| `INFLUXDB_ORG` | InfluxDB organization name |
| `INFLUXDB_BUCKET` | InfluxDB bucket name |
| `MODELS_CACHE_PATH` | Absolute path to the HuggingFace model cache directory. This directory is large; sharing it across containers avoids redundant downloads. |
| `DEVICE` | Inference device: `cpu`, `cuda:0` (NVIDIA GPU), or `mps` (Apple Silicon) |

> Note: `UVICORN_WORKERS` must be set to `1`. The services rely on module-level state that is incompatible with multiple worker processes.

### 4. Set Up the Python Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=$(pwd)
```

If individual services have their own requirements files, install those as needed. The `PYTHONPATH` export ensures all internal package imports resolve correctly. Add this export to your shell profile or activate script if you work on this project frequently.

### 5. Create the Docker Network

The `aleutian-shared` network must exist before starting services. InfluxDB and other Aleutian components are expected to be reachable on this network.

```bash
docker network create aleutian-shared 2>/dev/null || true
```

This command is idempotent — it will not fail if the network already exists.

### 6. Start Services

```bash
docker-compose up -d
# or, if using Podman:
podman-compose up -d
```

### 7. Verify Service Health

Once services are running, confirm each one is healthy:

```bash
# Orchestration gateway
curl http://localhost:12700/health

# Trading service
curl http://localhost:12132/health

# Metrics service
curl http://localhost:12702/health

# Data service (Go)
curl http://localhost:12701/health
```

Each endpoint should return a `200 OK` response. If any service is not responding, check its container logs with `docker logs <container-name>`.

---

## Running Tests

### Full Test Suite

```bash
python -m pytest tests/ orchestration/tests/ -x -q
```

### Individual Test Suites

```bash
# Metrics tests
python -m pytest tests/metrics/ -x -q

# Orchestration tests
python -m pytest orchestration/tests/ -x -q

# Shared module tests
python -m pytest tests/shared/ -x -q
```

### Go Tests (Data Service)

```bash
cd data && go test -v ./...
```

---

## Running Individual Services Without Docker

Use the following commands to run services directly for faster iteration during development. Ensure your `.env` is sourced and `PYTHONPATH` is set before running.

```bash
# Forecast gateway (default port 8000, adjust as needed)
uvicorn forecast.main:app --host 0.0.0.0 --port 8000

# Trading service
uvicorn trading.main:app --host 0.0.0.0 --port 9000

# Metrics service
uvicorn metrics.main:app --host 0.0.0.0 --port 8000

# Data service (Go)
cd data && go run main.go
```

> When running services individually, they will not benefit from Docker-level networking. Ensure that dependent services (such as InfluxDB) are reachable from your host machine.

---

## Port Allocation

| Port | Service |
|---|---|
| 12700 | Orchestration gateway |
| 12701 | Data service (Go) |
| 12702 | Metrics service |
| 12710-12717 | Chronos model inference workers |
| 12720-12721 | TimesFM model inference workers |
| 12132 | Trading service |
| 12780 | UI |

Check your `.env` file if any of these ports conflict with services already running on your machine.

---

## Common Troubleshooting

**"InfluxDB not ready" errors on startup**

InfluxDB must be running and attached to the `aleutian-shared` Docker network before Sapheneia services start. Verify it is running with `docker ps` and confirm its network attachment with `docker network inspect aleutian-shared`.

**Model downloads are slow on first run**

The first run will download model weights from HuggingFace, which can be several gigabytes. Set `MODELS_CACHE_PATH` to a directory on a fast, high-capacity drive and mount it as a shared volume across containers to avoid re-downloading on subsequent runs.

**Import errors when running services directly**

Ensure `PYTHONPATH` includes the repository root:

```bash
export PYTHONPATH=$(pwd)
```

This must be set in every shell session where you run the services. Consider adding it to your shell profile or to the `.venv/bin/activate` script.

**Port conflicts**

If a service fails to bind to its assigned port, another process is likely using that port. Check your `.env` for port assignments and use `lsof -i :<port>` (macOS/Linux) to identify the conflicting process.

**Multiple workers causing state errors**

`UVICORN_WORKERS` must be `1`. Running multiple workers will cause undefined behavior due to module-level shared state in the services. Do not override this value without understanding the implications.
