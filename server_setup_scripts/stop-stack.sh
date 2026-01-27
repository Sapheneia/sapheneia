#!/bin/bash
# =============================================================================
# Stop Sapheneia + Aleutian Stack
# =============================================================================

PROJECTS_DIR="${PROJECTS_DIR:-$HOME/projects}"

echo "Stopping stack..."

cd "$PROJECTS_DIR/AleutianFOSS"
aleutian stack stop 2>/dev/null || podman-compose down

cd "$PROJECTS_DIR/sapheneia"
podman-compose down

echo "✅ All services stopped."
