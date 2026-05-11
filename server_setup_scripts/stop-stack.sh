#!/bin/bash
# =============================================================================
# Stop Sapheneia + AleutianFOSS-TimeSeries Stack
# =============================================================================
#
# Environment overrides (optional):
#   ALEUTIAN_TIMESERIES_DIR   Path to AleutianFOSS-TimeSeries repo
#                             Default: sibling directory named AleutianFOSS-TimeSeries
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAPHENEIA_DIR="$(dirname "$SCRIPT_DIR")"
ALEUTIAN_DIR="${ALEUTIAN_TIMESERIES_DIR:-$(dirname "$SAPHENEIA_DIR")/AleutianFOSS-TimeSeries}"

echo "Stopping AleutianFOSS-TimeSeries..."
if [[ -f "$ALEUTIAN_DIR/podman-compose.yml" ]]; then
    cd "$ALEUTIAN_DIR" && podman-compose down
else
    echo "  Warning: AleutianFOSS-TimeSeries not found at $ALEUTIAN_DIR, skipping."
fi

echo "Stopping Sapheneia..."
cd "$SAPHENEIA_DIR" && podman-compose down

echo "All services stopped."
