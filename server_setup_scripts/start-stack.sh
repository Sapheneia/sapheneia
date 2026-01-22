#!/bin/bash
# =============================================================================
# Start Sapheneia + Aleutian Stack (DIGITS)
# =============================================================================
# Quick start script for daily use after initial setup.
#
# Usage:
#   ./scripts/start-stack.sh [--rebuild]
# =============================================================================

set -e

PROJECTS_DIR="${PROJECTS_DIR:-$HOME/projects}"
REBUILD=false

[[ "$1" == "--rebuild" ]] && REBUILD=true

# Ensure env vars are set
export ORCHESTRATOR_URL="${ORCHESTRATOR_URL:-http://localhost:12700}"
export SAPHENEIA_API_KEY="${SAPHENEIA_API_KEY:-default_trading_api_key_please_change}"

echo "🚀 Starting Sapheneia + Aleutian Stack..."

# 1. Sapheneia
echo "[1/3] Starting Sapheneia..."
cd "$PROJECTS_DIR/sapheneia"
[ "$REBUILD" = true ] && podman-compose build
podman-compose up -d forecast forecast-chronos-t5-tiny trading data

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
