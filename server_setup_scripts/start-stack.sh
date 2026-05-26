#!/bin/bash
# =============================================================================
# Start Sapheneia + AleutianFOSS-TimeSeries Stack
# =============================================================================
# Quick start script for daily use after initial setup.
#
# Usage:
#   ./server_setup_scripts/start-stack.sh [OPTIONS]
#
# Options:
#   --rebuild    Rebuild containers before starting
#   --gpu        Enable GPU support (NVIDIA)
#   --cpu        Force CPU mode (default if no GPU detected)
#
# Environment overrides (optional):
#   ALEUTIAN_TIMESERIES_DIR   Path to AleutianFOSS-TimeSeries repo
#                             Default: sibling directory named AleutianFOSS-TimeSeries
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAPHENEIA_DIR="$(dirname "$SCRIPT_DIR")"
ALEUTIAN_DIR="${ALEUTIAN_TIMESERIES_DIR:-$(dirname "$SAPHENEIA_DIR")/AleutianFOSS-TimeSeries}"

REBUILD=false
USE_GPU=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --rebuild) REBUILD=true; shift ;;
        --gpu) USE_GPU=true; shift ;;
        --cpu) USE_GPU=false; shift ;;
        *) shift ;;
    esac
done

# Validate AleutianFOSS-TimeSeries directory
if [[ ! -f "$ALEUTIAN_DIR/podman-compose.yml" ]]; then
    echo "Error: AleutianFOSS-TimeSeries not found at: $ALEUTIAN_DIR"
    echo "Set ALEUTIAN_TIMESERIES_DIR to the correct path and retry."
    exit 1
fi

# Auto-detect GPU
if ! $USE_GPU && command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected, enabling GPU support..."
    USE_GPU=true
fi

# Set device
if $USE_GPU; then
    export DEVICE="cuda"
    echo "Starting Sapheneia + AleutianFOSS-TimeSeries Stack (GPU mode)..."
else
    export DEVICE="cpu"
    echo "Starting Sapheneia + AleutianFOSS-TimeSeries Stack (CPU mode)..."
fi

# Ensure shared network exists
podman network inspect aleutian-shared &>/dev/null || podman network create aleutian-shared

# 1. Sapheneia
echo "[1/3] Starting Sapheneia..."
cd "$SAPHENEIA_DIR"
if [ "$REBUILD" = true ]; then
    podman-compose build forecast trading data
fi

if $USE_GPU; then
    podman-compose down forecast-chronos-t5-tiny 2>/dev/null || true
    podman-compose up -d forecast trading data
    # Start Chronos Tiny with GPU passthrough
    podman run -d --name forecast-chronos-t5-tiny \
        --network aleutian-shared \
        --device nvidia.com/gpu=all \
        -p 12710:8000 \
        -e MODEL_NAME=chronos \
        -e MODEL_VARIANT=amazon/chronos-t5-tiny \
        -e HF_HOME=/models_cache \
        -e DEVICE=cuda \
        -e PYTHONPATH=/app \
        -e API_SECRET_KEY="${API_SECRET_KEY:-change_me_in_production}" \
        -v "${SAPHENEIA_DIR}/forecast:/app/forecast:ro" \
        -v "${SAPHENEIA_DIR}/shared:/app/shared:ro" \
        -v "${SAPHENEIA_DIR}/logs:/app/logs" \
        -v "${MODELS_CACHE_PATH:-${SAPHENEIA_DIR}/models_cache}:/models_cache" \
        localhost/sapheneia_forecast 2>/dev/null || \
        echo "  Note: GPU container may already be running"
else
    podman-compose up -d forecast forecast-chronos-t5-tiny trading data
fi

# 2. AleutianFOSS-TimeSeries
echo "[2/3] Starting AleutianFOSS-TimeSeries..."
cd "$ALEUTIAN_DIR"
if [ "$REBUILD" = true ]; then
    podman-compose build orchestrator data-fetcher
fi
podman-compose up -d

# 3. Reconnect data service
echo "[3/3] Finalizing..."
sleep 5
cd "$SAPHENEIA_DIR"
podman restart sapheneia-data 2>/dev/null || true

# Health check
echo ""
echo "Service Status:"
sleep 5
for svc in "localhost:12210|Orchestrator" "localhost:12001|Data Fetcher" "localhost:12700|Sapheneia Forecast" "localhost:12132|Sapheneia Trading" "localhost:12130|InfluxDB"; do
    IFS='|' read -r addr name <<< "$svc"
    curl -s "http://$addr/health" > /dev/null 2>&1 && echo "  OK  $name" || echo "  ... $name (still starting)"
done

echo ""
echo "Stack is running."
echo ""
echo "Observability:"
echo "  Grafana:  http://localhost:3000"
echo "  Jaeger:   http://localhost:16686"
echo "  Prometheus: http://localhost:9090"
