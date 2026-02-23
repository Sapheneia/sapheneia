#!/bin/bash
# =============================================================================
# Start Sapheneia + Aleutian Stack (DIGITS)
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
# =============================================================================

set -e

PROJECTS_DIR="${PROJECTS_DIR:-$HOME/projects}"
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

# Auto-detect GPU if not specified
if ! $USE_GPU && command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        echo "🎮 NVIDIA GPU detected, enabling GPU support..."
        USE_GPU=true
    fi
fi

# Ensure env vars are set
export ORCHESTRATOR_URL="${ORCHESTRATOR_URL:-http://localhost:12700}"
export SAPHENEIA_API_KEY="${SAPHENEIA_API_KEY:-change_me_in_production_abc123}"
export SAPHENEIA_TRADING_API_KEY="${SAPHENEIA_TRADING_API_KEY:-change_me_trading_key_abc123}"

# Set device based on GPU flag
if $USE_GPU; then
    export DEVICE="cuda"
    GPU_FLAG="--device nvidia.com/gpu=all"
    echo "🚀 Starting Sapheneia + Aleutian Stack (GPU mode)..."
else
    export DEVICE="cpu"
    GPU_FLAG=""
    echo "🚀 Starting Sapheneia + Aleutian Stack (CPU mode)..."
fi

# 1. Sapheneia
echo "[1/3] Starting Sapheneia..."
cd "$PROJECTS_DIR/sapheneia"
[ "$REBUILD" = true ] && podman-compose build

# Start containers (with GPU if available)
if $USE_GPU; then
    # Stop existing containers first
    podman-compose down forecast-chronos-t5-tiny 2>/dev/null || true

    # Start with GPU support using podman directly for the model container
    podman-compose up -d forecast trading data

    # Start chronos with GPU
    podman run -d --name forecast-chronos-t5-tiny \
        --network sapheneia_aleutian-network \
        --device nvidia.com/gpu=all \
        -p 12710:8000 \
        -e API_HOST=0.0.0.0 \
        -e API_PORT=8000 \
        -e MODEL_NAME=chronos \
        -e MODEL_VARIANT=amazon/chronos-t5-tiny \
        -e HF_HOME=/models_cache \
        -e DEVICE=cuda \
        -e PYTHONPATH=/app \
        -e API_SECRET_KEY="${SAPHENEIA_API_KEY}" \
        -v "$(pwd)/forecast:/app/forecast" \
        -v "$(pwd)/logs:/app/logs" \
        -v "${MODELS_CACHE_PATH:-$(pwd)/models_cache}:/models_cache" \
        sapheneia_forecast-chronos-t5-tiny 2>/dev/null || \
    echo "  Note: Container may already be running or image name differs"
else
    podman-compose up -d forecast forecast-chronos-t5-tiny trading data
fi

# 2. AleutianFOSS
echo "[2/3] Starting AleutianFOSS..."
cd "$PROJECTS_DIR/AleutianFOSS"
if [ "$REBUILD" = true ]; then
    go build -o aleutian ./cmd/aleutian
    sudo cp aleutian /usr/local/bin/
    podman-compose build orchestrator
fi
aleutian stack start --forecast-mode sapheneia --skip-model-check

# 3. Reconnect
echo "[3/3] Finalizing..."
sleep 5
cd "$PROJECTS_DIR/sapheneia"
podman restart sapheneia-data 2>/dev/null || true

# Health check
echo ""
echo "Service Status:"
sleep 5
for svc in "localhost:12700|Forecast" "localhost:12710|Chronos" "localhost:12130|InfluxDB"; do
    IFS='|' read -r addr name <<< "$svc"
    curl -s "http://$addr/health" > /dev/null 2>&1 && echo "  ✓ $name" || echo "  ⚠ $name (starting...)"
done

echo ""
echo "✅ Stack running. Use: aleutian-eval --config strategies/spy_threshold_v1.yaml"
