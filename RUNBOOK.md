# Sapheneia Operations Runbook v2.2

## Table of Contents
1. [Quick Start](#quick-start)
2. [System Architecture](#system-architecture)
3. [Port Reference](#port-reference)
4. [Starting Services](#starting-services)
5. [Stopping Services](#stopping-services)
6. [Health Checks](#health-checks)
7. [Aleutian Integration](#aleutian-integration)
8. [Compute Modes](#compute-modes)
9. [Linux Server Deployment](#linux-server-deployment)
10. [GPU Deployment (RTX 5090)](#gpu-deployment-rtx-5090)
11. [NVIDIA Project Digits Deployment](#nvidia-project-digits-deployment)
12. [Simulation Storage](#simulation-storage)
13. [Debugging](#debugging)
14. [Common Issues](#common-issues)
15. [Testing](#testing)
16. [Logs](#logs)
17. [Performance Monitoring](#performance-monitoring)
18. [Maintenance](#maintenance)

---

## Quick Start

### Prerequisites

1. **Docker/Podman** installed and running
2. **aleutian-shared network** created:
   ```bash
   podman network create aleutian-shared
   ```
3. **Models cache** available at configured path (default: `/Volumes/ai_models/aleutian_data/models_cache`)

### Start Minimal System

```bash
cd /Users/jin/PycharmProjects/sapheneia

# Copy environment template (first time only)
cp .env.template .env

# Start core services + one model
podman-compose up -d forecast forecast-chronos-t5-tiny trading

# Wait for services to initialize (~30 seconds)
sleep 30

# Verify health
curl http://localhost:12700/health  # Gateway
curl http://localhost:12710/health  # Chronos tiny
curl http://localhost:12132/health  # Trading

# Test from Aleutian
cd /Users/jin/GolandProjects/AleutianFOSS
./aleutian timeseries forecast SPY --model "amazon/chronos-t5-tiny" --context 90 --horizon 10
```

### Stop All Services

```bash
cd /Users/jin/PycharmProjects/sapheneia
podman-compose stop
```

---

## System Architecture

### Service Topology

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          aleutian-shared network                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ALEUTIAN (Go)                          SAPHENEIA (Python)                 │
│  ────────────────                       ─────────────────────              │
│                                                                            │
│  ┌───────────────────┐                 ┌───────────────────────┐          │
│  │ orchestrator      │────────────────▶│ sapheneia-forecast    │          │
│  │ :12210            │  /orchestration │ :8000 (gateway)       │          │
│  │                   │  /v1/timeseries └──────────┬────────────┘          │
│  └───────────────────┘                            │                        │
│                                                   │ routes by model        │
│  ┌───────────────────┐                 ┌─────────▼─────────────┐          │
│  │ influxdb          │                 │                       │          │
│  │ :12130            │◀────────────────│ Model Containers      │          │
│  └───────────────────┘                 │ ───────────────────── │          │
│                                        │ chronos-t5-*: 8100-04 │          │
│  ┌───────────────────┐                 │ chronos-bolt-*: 8105-7│          │
│  │ data-fetcher      │                 │ timesfm-*: 8200-8299  │          │
│  │ :12001            │                 │ moirai-*: 8300-8399   │          │
│  └───────────────────┘                 │ granite-*: 8400-8499  │          │
│                                        │ moment-*: 8500-8599   │          │
│  ┌───────────────────┐                 │ yinglong-*: 8600-8699 │          │
│  │ observability     │                 └───────────────────────┘          │
│  │ jaeger:16686      │                                                     │
│  │ prometheus:9090   │                 ┌───────────────────────┐          │
│  │ grafana:3000      │                 │ sapheneia-trading     │          │
│  └───────────────────┘                 │ :12132 (ext) / :9000  │          │
│                                        └───────────────────────┘          │
│                                                                            │
│                                        ┌───────────────────────┐          │
│                                        │ sapheneia-data        │          │
│                                        │ :8001                 │          │
│                                        └───────────────────────┘          │
│                                                                            │
│                                        ┌───────────────────────┐          │
│                                        │ sapheneia-ui          │          │
│                                        │ :8080                 │          │
│                                        └───────────────────────┘          │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Core Services

| Service | Container Name | Port(s) | Purpose |
|---------|----------------|---------|---------|
| **Forecast Gateway** | sapheneia-forecast | 12700 | Routes requests to model containers |
| **Trading API** | sapheneia-trading | 12132 (ext) / 9000 (int) | Trading strategy execution |
| **Data Service** | sapheneia-data | 12701 | Yahoo Finance data ingestion |
| **UI** | sapheneia-ui | 12780 | Web interface |
| **Metrics** | sapheneia-metrics | 12702 | Financial metrics API |

### Model Containers

| Model | Container | Port | Parameters |
|-------|-----------|------|------------|
| Chronos T5 Tiny | forecast-chronos-t5-tiny | 12710 | 8M |
| Chronos T5 Mini | forecast-chronos-t5-mini | 12711 | 20M |
| Chronos T5 Small | forecast-chronos-t5-small | 12712 | 46M |
| Chronos T5 Base | forecast-chronos-t5-base | 12713 | 200M |
| Chronos T5 Large | forecast-chronos-t5-large | 12714 | 710M |
| Chronos Bolt Mini | forecast-chronos-bolt-mini | 12715 | Fast mini |
| Chronos Bolt Small | forecast-chronos-bolt-small | 12716 | Fast small |
| Chronos Bolt Base | forecast-chronos-bolt-base | 12717 | Fast base |
| TimesFM 2.0 | forecast-timesfm-2-0 | 12720 | 500M |

---

## Port Reference

All ports are configured in `.env` file for centralized management.

### Port Allocation Scheme

Uses the 127xx range to avoid collisions, consistent with Aleutian's 12xxx scheme.

| Range | Family | Description |
|-------|--------|-------------|
| 12700 | Gateway | Orchestration gateway (routes to models) |
| 12701 | Data | Data service (Yahoo Finance) |
| 12702 | Metrics | Financial metrics API |
| 12710-12719 | Chronos | Amazon Chronos T5 + Bolt |
| 12720-12729 | TimesFM | Google TimesFM 2.0/2.5 |
| 12730-12739 | Moirai | Salesforce Moirai |
| 12740-12749 | Granite | IBM Granite TTM |
| 12750-12759 | Moment | AutoLab Moment |
| 12760-12769 | Yinglong | Alibaba Yinglong |
| 12770-12779 | Other | Lag-Llama, Kairos, etc. |
| 12780 | UI | Web interface |
| 12132 | Trading | Trading strategies API |

### Aleutian Ports (for reference)

| Port | Service |
|------|---------|
| 12210 | Aleutian Orchestrator |
| 12130 | InfluxDB |
| 12001 | Data Fetcher |

### Quick Port Reference

```
Gateway:        12700
Data:           12701
Metrics:        12702
Chronos T5:     12710-12714 (tiny→large)
Chronos Bolt:   12715-12717 (mini→base)
TimesFM:        12720-12721
Trading:        12132
UI:             12780
```

---

## Starting Services

### Option 1: Start Specific Models (Recommended)

```bash
# Start gateway + specific model
podman-compose up -d forecast forecast-chronos-t5-tiny

# Add more models as needed
podman-compose up -d forecast-chronos-t5-base forecast-chronos-bolt-base

# Start with trading
podman-compose up -d forecast forecast-chronos-t5-tiny trading
```

### Option 2: Start by Model Family

```bash
# All Chronos T5 models
podman-compose up -d \
  forecast-chronos-t5-tiny \
  forecast-chronos-t5-mini \
  forecast-chronos-t5-small \
  forecast-chronos-t5-base \
  forecast-chronos-t5-large

# All Chronos Bolt models
podman-compose up -d \
  forecast-chronos-bolt-mini \
  forecast-chronos-bolt-small \
  forecast-chronos-bolt-base
```

### Option 3: Full Stack

```bash
# Start everything (warning: resource intensive)
podman-compose up -d
```

### Startup Verification

```bash
# Check running containers
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Watch logs during startup
podman-compose logs -f forecast-chronos-t5-tiny

# Wait for "Application startup complete"
```

---

## Stopping Services

### Stop Specific Services

```bash
# Stop one model
podman-compose stop forecast-chronos-t5-tiny

# Stop multiple
podman-compose stop forecast-chronos-t5-tiny forecast-chronos-t5-mini

# Stop all Chronos
podman stop $(podman ps -q --filter "name=forecast-chronos")
```

### Stop All

```bash
# Stop (preserves state)
podman-compose stop

# Stop and remove containers (preserves volumes)
podman-compose down

# Full cleanup including volumes (WARNING: deletes data)
podman-compose down -v
```

---

## Health Checks

### Quick Health Check Script

```bash
#!/bin/bash
# save as: check-health.sh

echo "=== Sapheneia Health Check ==="
echo ""

check_service() {
  local name=$1
  local url=$2
  if curl -sf "$url" > /dev/null 2>&1; then
    echo "  $name: ✅ UP"
  else
    echo "  $name: ❌ DOWN"
  fi
}

echo "Core Services:"
check_service "Gateway (12700)" "http://localhost:12700/health"
check_service "Trading (12132)" "http://localhost:12132/health"
check_service "Data (12701)" "http://localhost:12701/health"
check_service "UI (12780)" "http://localhost:12780/health"

echo ""
echo "Chronos Models:"
for port in 12710 12711 12712 12713 12714 12715 12716 12717; do
  status=$(curl -sf "http://localhost:${port}/health" | jq -r '.service // "unknown"' 2>/dev/null)
  if [ -n "$status" ] && [ "$status" != "null" ]; then
    echo "  Port ${port}: ✅ $status"
  fi
done
```

### Check Model Status

```bash
# Check if model is initialized and ready
curl http://localhost:12710/forecast/v1/chronos/status \
  -H "Authorization: Bearer $(grep API_SECRET_KEY .env | cut -d= -f2)"
```

### End-to-End Test

```bash
# Test unified predict endpoint
curl -X POST http://localhost:12700/orchestration/v1/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(grep API_SECRET_KEY .env | cut -d= -f2)" \
  -d '{
    "request_id": "test-123",
    "ticker": "SPY",
    "model": "amazon/chronos-t5-tiny",
    "context": {
      "values": [450.0, 451.2, 449.8, 452.1, 453.5],
      "period": "1d",
      "source": "manual",
      "start_date": "2025-12-25",
      "end_date": "2025-12-30",
      "field": "close"
    },
    "horizon": {
      "length": 5,
      "period": "1d"
    }
  }'

# Test legacy endpoint
curl -X POST http://localhost:12700/v1/timeseries/forecast \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(grep API_SECRET_KEY .env | cut -d= -f2)" \
  -d '{
    "name": "SPY",
    "model": "amazon/chronos-t5-tiny",
    "context_period_size": 50,
    "forecast_period_size": 10
  }'
```

---

## Aleutian Integration

### Configuration

Aleutian connects to Sapheneia via the `aleutian-shared` Docker network. Sapheneia is **OPTIONAL** - Aleutian can run in standalone mode without it.

**Aleutian Environment Variables** (set in AleutianFOSS):
```bash
# In podman-compose.timeseries.yml or .env

# Primary URLs (recommended)
SAPHENEIA_ORCHESTRATION_URL=http://sapheneia-forecast:8000  # For distributed
SAPHENEIA_ORCHESTRATION_URL=http://localhost:12210          # For standalone
SAPHENEIA_TRADING_URL=http://sapheneia-trading:9000         # For distributed
SAPHENEIA_TRADING_URL=http://localhost:12132                # For standalone

# Legacy URLs (deprecated, still supported for backwards compatibility)
ALEUTIAN_FORECAST_MODE=sapheneia
ALEUTIAN_TIMESERIES_TOOL=http://sapheneia-forecast:8000
SAPHENEIA_TRADING_SERVICE_URL=http://sapheneia-trading:9000

# API Key (required for trading)
SAPHENEIA_TRADING_API_KEY=your_trading_api_key
```

### Request Flow

1. **User** → `aleutian timeseries forecast SPY --model chronos-t5-tiny`
2. **Aleutian Evaluator** → ServiceRouter resolves URL based on deployment mode
3. **Request** → `POST http://sapheneia-forecast:8000/v1/timeseries/forecast` (legacy) or `/orchestration/v1/predict` (unified)
4. **Sapheneia Gateway** → Routes to `http://forecast-chronos-t5-tiny:8000`
5. **Model Container** → Runs inference, returns forecast
6. **Response** → Back through gateway to Aleutian to user

### Model Routing (Aleutian → Sapheneia)

Aleutian's `timeseries.go` normalizes model names and routes:

| User Input | Normalized | Sapheneia Container |
|------------|------------|---------------------|
| `amazon/chronos-t5-tiny` | `chronos-t5-tiny` | `forecast-chronos-t5-tiny:8000` (internal) / `:12710` (external) |
| `Chronos-T5-Base` | `chronos-t5-base` | `forecast-chronos-t5-base:8000` (internal) / `:12713` (external) |
| `google/timesfm-2.0-500m` | `timesfm-2-0-500m` | `forecast-timesfm-2-0:8000` (internal) / `:12720` (external) |

### CLI Flags

| Flag | Description | Values | Default |
|------|-------------|--------|---------|
| `--api-version` | API version to use | `legacy`, `unified` | `legacy` |
| `--deployment-mode` | Deployment topology | `standalone`, `distributed` | `standalone` |
| `--compute-mode` | **DEPRECATED** - use `--api-version` | `legacy`, `unified` | `legacy` |

### Deployment Modes

| Mode | Description | URLs |
|------|-------------|------|
| `standalone` | Local development, localhost ports | `http://localhost:12210`, `http://localhost:12132` |
| `distributed` | Kubernetes/Docker network | `http://sapheneia-orchestration:8000`, `http://sapheneia-trading:8000` |

### Testing Integration

```bash
# From Aleutian CLI - simple forecast
./aleutian timeseries forecast SPY \
  --model "amazon/chronos-t5-tiny" \
  --context 90 \
  --horizon 10

# Run backtest with scenario file (uses legacy API by default)
./aleutian evaluation run --config strategies/spy_threshold_v1.yaml

# Run backtest with unified API (includes request/response tracing)
./aleutian evaluation run --config strategies/spy_threshold_v1.yaml --api-version unified

# Run backtest in distributed mode (e.g., for Kubernetes)
./aleutian evaluation run --config strategies/spy_threshold_v1.yaml \
  --api-version unified \
  --deployment-mode distributed

# DEPRECATED: Using --compute-mode (still works but logs warning)
./aleutian evaluation run --config strategies/spy_threshold_v1.yaml --compute-mode unified
```

---

## Compute Modes

Aleutian supports two compute modes for calling Sapheneia:

### Legacy Mode (Default)

Uses the original `/v1/timeseries/forecast` endpoint.

**Request:**
```json
{
  "name": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "context_period_size": 252,
  "forecast_period_size": 10,
  "recent_data": [450.0, 451.2, ...]
}
```

**Response:**
```json
{
  "name": "SPY",
  "forecast": [454.2, 455.0, ...],
  "message": "Success"
}
```

**When to use:** Production backtests, proven stable.

### Unified Mode (New)

Uses the new `/orchestration/v1/predict` endpoint with full request tracing.

**Request:**
```json
{
  "request_id": "run-123-SPY-20250615-789",
  "timestamp": "2026-01-20T14:30:00Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "context": {
    "values": [450.0, 451.2, ...],
    "period": "1d",
    "source": "influxdb",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "field": "close"
  },
  "horizon": {"length": 10, "period": "1d"},
  "params": {"quantiles": [0.1, 0.5, 0.9]}
}
```

**Response:**
```json
{
  "request_id": "run-123-SPY-20250615-789",
  "response_id": "resp-456",
  "timestamp": "2026-01-20T14:30:02Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "forecast": {
    "values": [454.2, 455.0, ...],
    "period": "1d",
    "start_date": "2026-01-20",
    "end_date": "2026-01-29"
  },
  "quantiles": [
    {"quantile": 0.1, "values": [452.1, ...]},
    {"quantile": 0.5, "values": [454.2, ...]},
    {"quantile": 0.9, "values": [456.3, ...]}
  ],
  "metadata": {
    "inference_time_ms": 245,
    "device": "cuda:0",
    "model_family": "chronos"
  }
}
```

**When to use:** Debugging, performance analysis, audit trails, uncertainty quantification.

### How to Set Compute Mode

**Option 1: In Scenario YAML**
```yaml
# strategies/spy_threshold_v1.yaml
forecast:
  model: "amazon/chronos-t5-tiny"
  context_size: 252
  horizon_size: 10
  compute_mode: "unified"        # <-- Add this
  quantiles: [0.1, 0.5, 0.9]     # <-- Optional
```

**Option 2: CLI Override**
```bash
# Override to unified regardless of YAML setting
./aleutian evaluate run --config scenario.yaml --compute-mode unified

# Override to legacy
./aleutian evaluate run --config scenario.yaml --compute-mode legacy
```

### Comparison Table

| Feature | Legacy | Unified |
|---------|--------|---------|
| Endpoint | `/v1/timeseries/forecast` | `/orchestration/v1/predict` |
| Request tracing | ❌ No | ✅ request_id + response_id |
| Context metadata | ❌ No | ✅ source, period, dates |
| Quantile forecasts | ❌ No | ✅ Optional |
| Inference timing | ❌ No | ✅ inference_time_ms |
| Device info | ❌ No | ✅ cpu/cuda/mps |
| Status | Stable | New (Jan 2026) |

---

## Linux Server Deployment

Step-by-step instructions for deploying Sapheneia + Aleutian on a headless Linux server via SSH.

### Prerequisites

- Ubuntu 22.04+ or similar Linux distro
- Docker or Podman installed
- At least 16GB RAM (32GB+ recommended for multiple models)
- SSH access to server

### Step 1: SSH to Server

```bash
# From your local machine
ssh your-username@your-server-ip

# Or with key
ssh -i ~/.ssh/your-key your-username@your-server-ip
```

### Step 2: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Podman (recommended) or Docker
sudo apt install -y podman podman-compose

# Verify installation
podman --version
podman-compose --version

# Install Go 1.21+ for Aleutian
wget https://go.dev/dl/go1.21.6.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.6.linux-amd64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc
go version

# Install Git
sudo apt install -y git jq curl
```

### Step 3: Create Working Directory

```bash
# Create project directory
mkdir -p ~/projects
cd ~/projects
```

### Step 4: Clone Repositories

```bash
# Clone Sapheneia
git clone https://github.com/YOUR_ORG/sapheneia.git
cd sapheneia

# Clone Aleutian (in separate directory)
cd ~/projects
git clone https://github.com/YOUR_ORG/AleutianFOSS.git
cd AleutianFOSS
```

### Step 5: Create Docker Network

```bash
# Create shared network for both stacks
podman network create aleutian-shared

# Verify
podman network ls
```

### Step 6: Configure Sapheneia

```bash
cd ~/projects/sapheneia

# Copy environment template
cp .env.template .env

# Edit configuration
nano .env
```

**Key `.env` settings:**
```bash
# API Keys (generate secure values)
API_SECRET_KEY=your_secure_api_key_here
SAPHENEIA_TRADING_API_KEY=your_trading_api_key_here

# Models cache directory (create if needed)
MODELS_CACHE_DIR=/home/your-username/models_cache

# Ports (127xx scheme)
ORCHESTRATION_PORT=12700
CHRONOS_T5_TINY_PORT=12710
TRADING_API_PORT=12132
```

### Step 7: Create Models Cache Directory

```bash
# Create cache directory
mkdir -p ~/models_cache

# Update .env with correct path
sed -i 's|MODELS_CACHE_DIR=.*|MODELS_CACHE_DIR=/home/'$(whoami)'/models_cache|' .env

# Verify
grep MODELS_CACHE_DIR .env
```

### Step 8: Start Sapheneia Services

```bash
cd ~/projects/sapheneia

# Start minimal stack (gateway + one model + trading)
podman-compose up -d forecast forecast-chronos-t5-tiny trading

# Watch startup logs (wait for "Application startup complete")
podman-compose logs -f forecast-chronos-t5-tiny

# Press Ctrl+C when ready, then verify
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Step 9: Verify Sapheneia Health

```bash
# Check gateway
curl http://localhost:12700/health

# Check model
curl http://localhost:12710/health

# Check trading
curl http://localhost:12132/health

# Test forecast (should return JSON with forecast array)
curl -X POST http://localhost:12700/v1/timeseries/forecast \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(grep API_SECRET_KEY .env | cut -d= -f2)" \
  -d '{
    "name": "TEST",
    "model": "amazon/chronos-t5-tiny",
    "context_period_size": 10,
    "forecast_period_size": 5,
    "recent_data": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
  }'
```

### Step 10: Build Aleutian

```bash
cd ~/projects/AleutianFOSS

# Build the binary
go build -o aleutian ./cmd/aleutian

# Verify
./aleutian --help
```

### Step 11: Configure Aleutian

```bash
cd ~/projects/AleutianFOSS

# Set environment variables
export ORCHESTRATOR_URL=http://localhost:12700
export SAPHENEIA_TRADING_SERVICE_URL=http://localhost:12132
export SAPHENEIA_TRADING_API_KEY=$(grep SAPHENEIA_TRADING_API_KEY ~/projects/sapheneia/.env | cut -d= -f2)

# Or add to ~/.bashrc for persistence
echo 'export ORCHESTRATOR_URL=http://localhost:12700' >> ~/.bashrc
echo 'export SAPHENEIA_TRADING_SERVICE_URL=http://localhost:12132' >> ~/.bashrc
source ~/.bashrc
```

### Step 12: Start Aleutian Stack (InfluxDB)

```bash
cd ~/projects/AleutianFOSS

# Start InfluxDB and data services
podman-compose -f podman-compose.yml up -d user-influxdb

# Wait for startup
sleep 10

# Verify InfluxDB
curl http://localhost:12130/health
```

### Step 13: Test End-to-End

```bash
cd ~/projects/AleutianFOSS

# Test forecast command
./aleutian timeseries forecast SPY \
  --model "amazon/chronos-t5-tiny" \
  --context 30 \
  --horizon 5

# Run a backtest (if you have a scenario file)
./aleutian evaluate run --config strategies/example.yaml --compute-mode unified
```

### Step 14: Run as Background Services (Optional)

```bash
# Create systemd service for Sapheneia
sudo tee /etc/systemd/system/sapheneia.service << 'EOF'
[Unit]
Description=Sapheneia Forecast Services
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/projects/sapheneia
ExecStart=/usr/bin/podman-compose up
ExecStop=/usr/bin/podman-compose stop
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable sapheneia
sudo systemctl start sapheneia

# Check status
sudo systemctl status sapheneia
```

### Quick Reference Commands (Linux Server)

```bash
# SSH to server
ssh user@server

# Check services
podman ps

# View logs
podman logs -f forecast-chronos-t5-tiny

# Restart services
cd ~/projects/sapheneia && podman-compose restart

# Stop all
cd ~/projects/sapheneia && podman-compose stop

# Check disk space
df -h

# Check memory
free -h

# Check GPU (if applicable)
nvidia-smi
```

### Troubleshooting Linux Deployment

**Issue: Port already in use**
```bash
# Find what's using the port
sudo lsof -i :12700

# Kill if needed
sudo kill -9 <PID>
```

**Issue: Permission denied on models cache**
```bash
# Fix permissions
sudo chown -R $(whoami):$(whoami) ~/models_cache
chmod -R 755 ~/models_cache
```

**Issue: Out of memory**
```bash
# Check memory usage
free -h
podman stats

# Start fewer models
podman-compose up -d forecast forecast-chronos-t5-tiny trading
# Don't start the large models
```

**Issue: Container won't start after reboot**
```bash
# Recreate network
podman network create aleutian-shared

# Restart services
cd ~/projects/sapheneia && podman-compose up -d
```

---

## GPU Deployment (RTX 5090)

Step-by-step instructions for deploying Sapheneia with NVIDIA RTX 5090 GPU acceleration.

### Prerequisites

- NVIDIA RTX 5090 (or any CUDA-capable GPU)
- Ubuntu 22.04+ with kernel 6.5+
- NVIDIA Driver 550+ (for RTX 50 series)
- 32GB+ system RAM recommended

### Step 1: Install NVIDIA Drivers

```bash
# SSH to your server
ssh user@your-gpu-server

# Check if GPU is detected
lspci | grep -i nvidia

# Add NVIDIA repository
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:graphics-drivers/ppa
sudo apt update

# Install latest driver (550+ for RTX 5090)
sudo apt install -y nvidia-driver-550

# Reboot required
sudo reboot
```

### Step 2: Verify Driver Installation

```bash
# After reboot, verify
nvidia-smi

# Expected output shows:
# - Driver Version: 550.xx or higher
# - CUDA Version: 12.x
# - RTX 5090 with ~32GB VRAM
```

### Step 3: Install NVIDIA Container Toolkit

```bash
# Add NVIDIA container repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install toolkit
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure for Podman
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Verify CDI spec
nvidia-ctk cdi list
```

### Step 4: Configure Podman for GPU

```bash
# Test GPU access in container
podman run --rm --device nvidia.com/gpu=all \
  nvidia/cuda:12.3-base-ubuntu22.04 nvidia-smi

# Should show your RTX 5090
```

### Step 5: Update Sapheneia .env for GPU

```bash
cd ~/projects/sapheneia

# Edit .env
nano .env
```

**GPU-specific `.env` settings:**
```bash
# Enable GPU for all model containers
DEVICE=cuda:0

# For multi-GPU systems, you can assign specific GPUs:
# CHRONOS_DEVICE=cuda:0
# TIMESFM_DEVICE=cuda:1

# Increase batch size for GPU (faster inference)
BATCH_SIZE=32

# Enable TensorFloat-32 for RTX 50 series (faster)
TORCH_ALLOW_TF32=1
CUDA_ALLOW_TF32=1
```

### Step 6: Update docker-compose.yml for GPU

Add GPU device to model containers in `docker-compose.yml`:

```yaml
# Example for chronos-t5-tiny
forecast-chronos-t5-tiny:
  image: sapheneia-forecast:latest
  container_name: forecast-chronos-t5-tiny
  # ... existing config ...
  devices:
    - nvidia.com/gpu=all    # <-- Add this line
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
    - DEVICE=cuda:0
```

Or use the GPU-specific compose file if available:
```bash
# Start with GPU support
podman-compose -f docker-compose.gpu.yml up -d forecast forecast-chronos-t5-tiny
```

### Step 7: Start GPU-Accelerated Services

```bash
cd ~/projects/sapheneia

# Start with GPU
podman-compose up -d forecast forecast-chronos-t5-tiny trading

# Verify GPU is being used
podman logs forecast-chronos-t5-tiny 2>&1 | grep -i "device\|cuda\|gpu"

# Should see: "Using device: cuda:0" or similar
```

### Step 8: Verify GPU Inference

```bash
# Test forecast and check inference time
time curl -X POST http://localhost:12700/v1/timeseries/forecast \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(grep API_SECRET_KEY .env | cut -d= -f2)" \
  -d '{
    "name": "SPY",
    "model": "amazon/chronos-t5-tiny",
    "context_period_size": 252,
    "forecast_period_size": 30,
    "recent_data": '"$(python3 -c "import json; print(json.dumps([100+i*0.5 for i in range(252)]))")"'
  }'

# GPU inference should be 5-10x faster than CPU
# RTX 5090 expected: ~50-100ms for tiny model
```

### Step 9: Monitor GPU Usage

```bash
# Real-time GPU monitoring
watch -n 1 nvidia-smi

# Or use nvtop (more detailed)
sudo apt install -y nvtop
nvtop

# Check GPU memory per container
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```

### GPU Performance Tips

| Model Size | RTX 5090 Expected Time | Batch Size |
|------------|------------------------|------------|
| Chronos T5 Tiny | ~30-50ms | 32 |
| Chronos T5 Small | ~50-80ms | 32 |
| Chronos T5 Base | ~100-150ms | 16 |
| Chronos T5 Large | ~200-400ms | 8 |
| TimesFM 2.0 | ~150-250ms | 16 |

### Troubleshooting GPU

**Issue: CUDA out of memory**
```bash
# Check GPU memory
nvidia-smi

# Reduce batch size in .env
BATCH_SIZE=8

# Or run fewer models concurrently
podman-compose up -d forecast forecast-chronos-t5-tiny
# Don't start large models simultaneously
```

**Issue: GPU not detected in container**
```bash
# Regenerate CDI spec
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Restart podman
systemctl --user restart podman

# Verify
podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.3-base-ubuntu22.04 nvidia-smi
```

**Issue: Driver mismatch**
```bash
# Check driver/CUDA compatibility
nvidia-smi  # Shows driver CUDA version
nvcc --version  # Shows toolkit CUDA version (if installed)

# They should be compatible (driver CUDA >= toolkit CUDA)
```

---

## NVIDIA Project Digits Deployment

Instructions for deploying Sapheneia on NVIDIA Project Digits (GB10 Grace Blackwell Superchip).

### About Project Digits

- **Architecture**: ARM64 (aarch64)
- **GPU**: GB10 Grace Blackwell Superchip
- **Memory**: 128GB unified memory
- **AI Performance**: 1 PFLOP FP4
- **OS**: NVIDIA DGX OS (Ubuntu-based)

### Key Differences from x86 Deployment

| Aspect | x86 Linux | Project Digits |
|--------|-----------|----------------|
| Architecture | x86_64 | aarch64 (ARM64) |
| GPU | Discrete (PCIe) | Integrated (unified memory) |
| Memory | Separate CPU/GPU | Unified 128GB |
| Containers | Standard images | ARM64 images required |
| Driver | nvidia-driver-xxx | Pre-installed |

### Step 1: Connect to Project Digits

```bash
# SSH to your Digits device
ssh user@digits-hostname

# Verify architecture
uname -m
# Expected: aarch64

# Check GPU
nvidia-smi
# Should show GB10 Grace Blackwell
```

### Step 2: Verify Pre-installed Components

Project Digits comes with NVIDIA software pre-installed:

```bash
# Check Docker/container runtime
docker --version
# or
podman --version

# Check NVIDIA container toolkit
nvidia-ctk --version

# Check PyTorch (may be pre-installed)
python3 -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

### Step 3: Clone Repositories

```bash
# Create workspace
mkdir -p ~/projects && cd ~/projects

# Clone Sapheneia
git clone https://github.com/YOUR_ORG/sapheneia.git

# Clone Aleutian
git clone https://github.com/YOUR_ORG/AleutianFOSS.git
```

### Step 4: Build ARM64 Container Images

Project Digits requires ARM64-native container images:

```bash
cd ~/projects/sapheneia

# Build ARM64 images (multi-arch Containerfile required)
podman build --platform linux/arm64 -t sapheneia-forecast:arm64 -f Containerfile.forecast .

# Or use pre-built ARM64 images if available
# podman pull ghcr.io/your-org/sapheneia-forecast:arm64
```

### Step 5: Configure for Unified Memory

Project Digits has unified CPU/GPU memory - configure to take advantage:

```bash
cd ~/projects/sapheneia
cp .env.template .env
nano .env
```

**Digits-specific `.env` settings:**
```bash
# Device configuration for Grace Blackwell
DEVICE=cuda:0

# Leverage unified memory - can use larger context sizes
MAX_CONTEXT_SIZE=4096

# Batch size can be larger due to unified memory
BATCH_SIZE=64

# Enable memory-efficient attention
USE_FLASH_ATTENTION=true

# Models cache
MODELS_CACHE_DIR=/home/$(whoami)/models_cache
```

### Step 6: Create Docker Network

```bash
# Create shared network
podman network create aleutian-shared

# Verify
podman network ls
```

### Step 7: Start Services

```bash
cd ~/projects/sapheneia

# Start with ARM64 images
podman-compose up -d forecast forecast-chronos-t5-tiny trading

# Monitor startup
podman-compose logs -f forecast-chronos-t5-tiny
```

### Step 8: Build Aleutian for ARM64

```bash
cd ~/projects/AleutianFOSS

# Go cross-compiles automatically, just build
go build -o aleutian ./cmd/aleutian

# Verify
./aleutian --help
file aleutian
# Should show: ELF 64-bit LSB executable, ARM aarch64
```

### Step 9: Test End-to-End

```bash
cd ~/projects/AleutianFOSS

# Set environment
export ORCHESTRATOR_URL=http://localhost:12700
export SAPHENEIA_TRADING_API_KEY=$(grep SAPHENEIA_TRADING_API_KEY ~/projects/sapheneia/.env | cut -d= -f2)

# Test forecast
./aleutian timeseries forecast SPY \
  --model "amazon/chronos-t5-tiny" \
  --context 252 \
  --horizon 30

# Run backtest with unified mode
./aleutian evaluate run --config strategies/example.yaml --compute-mode unified
```

### Project Digits Performance Expectations

With GB10's 1 PFLOP FP4 performance and 128GB unified memory:

| Model | Expected Inference Time | Notes |
|-------|------------------------|-------|
| Chronos T5 Tiny | ~10-20ms | Extremely fast |
| Chronos T5 Large | ~50-100ms | Fits entirely in memory |
| TimesFM 2.0 | ~40-80ms | Optimized for Blackwell |
| Multiple models | Concurrent | 128GB allows many models loaded |

### Unique Advantages on Digits

1. **No memory transfers**: Unified memory eliminates CPU↔GPU copies
2. **Large context windows**: 128GB allows context_size=4096+
3. **Multi-model serving**: Load multiple large models simultaneously
4. **Energy efficient**: ARM + Blackwell = lower power consumption

### Troubleshooting Project Digits

**Issue: ARM64 image not found**
```bash
# Check available architectures
podman image inspect sapheneia-forecast:latest | jq '.[].Architecture'

# Build for ARM64 explicitly
podman build --platform linux/arm64 -t sapheneia-forecast:arm64 .
```

**Issue: PyTorch not using GPU**
```bash
# Verify CUDA availability
python3 -c "import torch; print('CUDA:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0))"

# Should show: CUDA: True, Device: NVIDIA GB10
```

**Issue: Model loading slow**
```bash
# First load downloads from HuggingFace - this is normal
# Subsequent loads use cache

# Check cache
ls -la ~/models_cache/

# Pre-download models
python3 -c "from transformers import AutoModel; AutoModel.from_pretrained('amazon/chronos-t5-tiny')"
```

---

## Simulation Storage

### Directory Structure

Simulations are stored at `SIMULATIONS_ROOT` (default: `/simulations`):

```
simulations/
├── forecasts/                    # Individual forecast results
│   └── {YYYY}/{MM}/{DD}/        # Date partitions
│       └── {ticker}/            # Asset (SPY, AAPL)
│           └── {model}/         # Model family
│               └── {version}/   # Model version
│                   └── forecast_{request_id}.json
│
├── backtests/                    # Backtest run outputs
│   └── {run_id}/
│       ├── config.json          # BacktestScenario
│       ├── summary.json         # Aggregate metrics
│       ├── trades.jsonl         # Trade log
│       └── equity_curve.csv     # Portfolio over time
│
├── strategies/                   # Strategy configs
│   └── {strategy_id}/
│       ├── config.json
│       └── performance.json
│
├── models/                       # Model metadata
│   └── {model_family}/
│       └── {variant}/
│           └── metrics.json
│
└── index/                        # Quick lookup indices
    ├── by_ticker.json
    ├── by_model.json
    └── runs.json
```

### Forecast File Schema

```json
{
  "request_id": "550e8400-e29b-...",
  "response_id": "660f9511-f30c-...",
  "timestamp": "2026-01-20T14:30:02Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "forecast": {
    "values": [454.2, 455.0, ...],
    "period": "1d",
    "start_date": "2026-01-20",
    "end_date": "2026-01-24"
  },
  "context_summary": {
    "length": 252,
    "period": "1d",
    "source": "influxdb"
  },
  "metadata": {
    "inference_time_ms": 245,
    "device": "cpu"
  }
}
```

### Querying Simulations

```bash
# List recent forecasts for SPY
ls simulations/forecasts/2026/01/*/SPY/

# Find all backtests
cat simulations/index/runs.json | jq '.[] | select(.ticker == "SPY")'

# Get summary of specific backtest
cat simulations/backtests/abc123/summary.json
```

---

## Debugging

### Step 1: Check Container Status

```bash
# List all Sapheneia containers
podman ps -a --filter "name=sapheneia" --filter "name=forecast-" \
  --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check specific container
podman ps --filter "name=forecast-chronos-t5-tiny"
```

### Step 2: Check Logs

```bash
# View last 50 lines
podman logs --tail 50 forecast-chronos-t5-tiny

# Follow logs
podman logs -f forecast-chronos-t5-tiny

# Search for errors
podman logs forecast-chronos-t5-tiny 2>&1 | grep -i error
```

### Step 3: Check Network

```bash
# Verify network exists
podman network ls | grep aleutian-shared

# Create if missing
podman network create aleutian-shared

# Check container network
podman network inspect aleutian-shared | jq '.[].Containers'
```

### Step 4: Check Volumes

```bash
# Verify code mounted
podman exec forecast-chronos-t5-tiny ls -la /app/forecast/

# Check models cache
podman exec forecast-chronos-t5-tiny ls -la /models_cache/
```

### Step 5: Interactive Debug

```bash
# Enter container
podman exec -it forecast-chronos-t5-tiny /bin/bash

# Inside container:
python --version
pip list | grep chronos
env | grep -E "(API_PORT|MODEL_VARIANT|DEVICE)"
curl http://localhost:8000/health
```

---

## Common Issues

### Issue 1: Container Won't Start

**Symptoms:** Container exits immediately

**Debug:**
```bash
podman logs forecast-chronos-t5-tiny
```

**Common causes:**
- Port conflict: Another service using the port
- Network missing: `podman network create aleutian-shared`
- Memory: Insufficient RAM for model

### Issue 2: Model Initialization Fails

**Symptoms:** `/status` returns `{"model_status": "error"}`

**Debug:**
```bash
podman logs forecast-chronos-t5-tiny 2>&1 | grep "initialization"
```

**Common causes:**
- Models cache not mounted or read-only
- HuggingFace authentication required
- Insufficient disk space

### Issue 3: Aleutian Can't Connect

**Symptoms:** `connection refused` from Aleutian

**Debug:**
```bash
# Check if container on correct network
podman network inspect aleutian-shared | grep forecast-chronos

# Test from Aleutian orchestrator
podman exec aleutian-go-orchestrator \
  curl -s http://forecast-chronos-t5-tiny:8000/health
```

**Fix:** Ensure both stacks use `aleutian-shared` network

### Issue 4: Old Code Running

**Symptoms:** Changes not reflected after code update

**Fix:**
```bash
# Python caches modules - must restart
podman-compose restart forecast-chronos-t5-tiny

# If that doesn't work, rebuild
podman-compose build forecast-chronos-t5-tiny
podman-compose up -d forecast-chronos-t5-tiny
```

---

## Testing

### Unit Tests

```bash
cd /Users/jin/PycharmProjects/sapheneia

# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=forecast/core --cov-report=html

# Specific test
pytest tests/test_legacy_adapters.py -v
```

### Integration Tests

```bash
# Test Chronos API directly
curl http://localhost:12710/health

# Test via gateway
curl -X POST http://localhost:12700/v1/timeseries/forecast \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(grep API_SECRET_KEY .env | cut -d= -f2)" \
  -d '{"name": "SPY", "model": "amazon/chronos-t5-tiny", "context_period_size": 50, "forecast_period_size": 10}'
```

---

## Logs

### Log Locations

```bash
# Container logs
podman logs <container_name>

# Application logs
ls -la /Users/jin/PycharmProjects/sapheneia/logs/

# Inside containers
podman exec <container_name> ls -la /app/logs/
```

### Useful Commands

```bash
# Follow with timestamps
podman logs -f --timestamps forecast-chronos-t5-tiny

# Since specific time
podman logs --since "2026-01-20T10:00:00" forecast-chronos-t5-tiny

# All forecast containers
for c in $(podman ps --filter "name=forecast-" -q); do
  echo "=== $(podman inspect $c --format '{{.Name}}') ==="
  podman logs --tail 5 $c 2>&1 | grep -i error
done
```

---

## Performance Monitoring

### Resource Usage

```bash
# Real-time stats
podman stats

# Specific container
podman stats forecast-chronos-t5-tiny

# Snapshot
podman stats --no-stream
```

### Inference Timing

```bash
# Check inference time in logs
podman logs forecast-chronos-t5-tiny 2>&1 | grep "inference_time"
```

---

## Maintenance

### Daily

- Check disk space: `df -h`
- Review error logs
- Verify health endpoints

### Weekly

- Restart containers to clear memory: `podman-compose restart`
- Review performance metrics
- Clean old simulation files

### Monthly

- Rebuild images: `podman-compose build`
- Clean unused containers: `podman container prune`
- Clean unused images: `podman image prune`
- Backup simulation data

### Backup

```bash
# Backup simulations
rsync -av /Users/jin/PycharmProjects/sapheneia/simulations/ /backup/simulations/

# Backup configuration
cp .env .env.backup
cp docker-compose.yml docker-compose.yml.backup
```

---

## Quick Reference

### Essential Commands

```bash
# Start minimal
podman-compose up -d forecast forecast-chronos-t5-tiny trading

# Check status
podman ps --filter "name=forecast"

# View logs
podman logs -f forecast-chronos-t5-tiny

# Stop
podman-compose stop

# Restart
podman-compose restart forecast-chronos-t5-tiny

# Rebuild
podman-compose build && podman-compose up -d
```

### Key Files

```
/Users/jin/PycharmProjects/sapheneia/
├── .env                    # Environment configuration
├── .env.template           # Configuration template
├── docker-compose.yml      # Service definitions
├── RUNBOOK.md              # This file
├── forecast/               # Forecast API code
│   ├── core/               # Shared infrastructure
│   └── models/             # Model implementations
├── trading/                # Trading API code
├── simulations/            # Forecast & backtest storage
└── logs/                   # Application logs
```

### Support

- Design docs: `docs/designs/aleutian_integration_v2.md`
- Model guide: `MODELS.md`
- Issues: GitHub repository
