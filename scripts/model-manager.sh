#!/bin/bash
# =============================================================================
# Model Manager - Sapheneia Forecast Container Management
# =============================================================================
# Automated management of forecast model containers including:
#   - Building container images
#   - Starting/stopping containers
#   - Initializing models
#   - Health checks and status
#
# Usage:
#   ./model-manager.sh list                    # List all models and their status
#   ./model-manager.sh start chronos-t5-tiny   # Start specific model
#   ./model-manager.sh start --all             # Start all models
#   ./model-manager.sh stop chronos-t5-tiny    # Stop specific model
#   ./model-manager.sh init chronos-t5-tiny    # Initialize model after start
#   ./model-manager.sh status                  # Show running containers
#   ./model-manager.sh build chronos-t5-tiny   # Build image for model
#   ./model-manager.sh pull chronos-t5-tiny    # Pre-download HuggingFace model
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAPHENEIA_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="${SAPHENEIA_DIR}/docker-compose.yml"

# Detect container runtime (podman preferred on DIGITS)
if command -v podman &> /dev/null; then
    RUNTIME="podman"
    COMPOSE_CMD="podman-compose"
elif command -v docker &> /dev/null; then
    RUNTIME="docker"
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Error: Neither podman nor docker found${NC}"
    exit 1
fi

# =============================================================================
# Model Registry
# =============================================================================
# Format: "slug|container_name|model_variant|port|model_family|status"
# Status: supported (in Sapheneia) or planned (in AleutianFOSS but no Sapheneia impl)

declare -a MODELS=(
    # Amazon Chronos T5 Series - SUPPORTED
    "chronos-t5-tiny|forecast-chronos-t5-tiny|amazon/chronos-t5-tiny|12710|chronos|supported"
    "chronos-t5-mini|forecast-chronos-t5-mini|amazon/chronos-t5-mini|12711|chronos|supported"
    "chronos-t5-small|forecast-chronos-t5-small|amazon/chronos-t5-small|12712|chronos|supported"
    "chronos-t5-base|forecast-chronos-t5-base|amazon/chronos-t5-base|12713|chronos|supported"
    "chronos-t5-large|forecast-chronos-t5-large|amazon/chronos-t5-large|12714|chronos|supported"

    # Amazon Chronos Bolt Series - SUPPORTED
    "chronos-bolt-mini|forecast-chronos-bolt-mini|amazon/chronos-bolt-mini|12715|chronos|supported"
    "chronos-bolt-small|forecast-chronos-bolt-small|amazon/chronos-bolt-small|12716|chronos|supported"
    "chronos-bolt-base|forecast-chronos-bolt-base|amazon/chronos-bolt-base|12717|chronos|supported"

    # Google TimesFM - SUPPORTED (but container commented in compose)
    "timesfm-2-0|forecast-timesfm-2-0|google/timesfm-2.0-500m-pytorch|12720|timesfm|supported"

    # Google TimesFM - PLANNED (no Sapheneia impl yet)
    "timesfm-1-0|forecast-timesfm-1-0|google/timesfm-1.0-200m|12721|timesfm|planned"
    "timesfm-2-5|forecast-timesfm-2-5|google/timesfm-2.5|12722|timesfm|planned"

    # Salesforce Moirai - PLANNED
    "moirai-1-0-small|forecast-moirai-1-0-small|salesforce/moirai-1.0-R-small|12730|moirai|planned"
    "moirai-1-1-small|forecast-moirai-1-1-small|salesforce/moirai-1.1-R-small|12731|moirai|planned"
    "moirai-1-1-base|forecast-moirai-1-1-base|salesforce/moirai-1.1-R-base|12732|moirai|planned"
    "moirai-1-1-large|forecast-moirai-1-1-large|salesforce/moirai-1.1-R-large|12733|moirai|planned"
    "moirai-2-0-small|forecast-moirai-2-0-small|salesforce/moirai-2.0-R-small|12734|moirai|planned"

    # IBM Granite - PLANNED
    "granite-ttm-r1|forecast-granite-ttm-r1|ibm/granite-timeseries-ttm-r1|12740|granite|planned"
    "granite-ttm-r2|forecast-granite-ttm-r2|ibm/granite-timeseries-ttm-r2|12741|granite|planned"

    # AutonLab Moment - PLANNED
    "moment-small|forecast-moment-small|AutonLab/MOMENT-1-small|12750|moment|planned"
    "moment-base|forecast-moment-base|AutonLab/MOMENT-1-base|12751|moment|planned"
    "moment-large|forecast-moment-large|AutonLab/MOMENT-1-large|12752|moment|planned"

    # Alibaba Yinglong - PLANNED
    "yinglong-6m|forecast-yinglong-6m|Yinglong/yinglong-6m|12760|yinglong|planned"
    "yinglong-50m|forecast-yinglong-50m|Yinglong/yinglong-50m|12761|yinglong|planned"

    # Other - PLANNED
    "lag-llama|forecast-lag-llama|time-series-foundation-models/Lag-Llama|12770|lagllama|planned"
)

# =============================================================================
# Helper Functions
# =============================================================================

log() {
    echo -e "$1"
}

get_model_field() {
    local slug="$1"
    local field="$2"  # 1=slug, 2=container, 3=variant, 4=port, 5=family, 6=status

    for model in "${MODELS[@]}"; do
        local m_slug=$(echo "$model" | cut -d'|' -f1)
        if [[ "$m_slug" == "$slug" ]]; then
            echo "$model" | cut -d'|' -f"$field"
            return 0
        fi
    done
    return 1
}

is_container_running() {
    local container="$1"
    $RUNTIME ps --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"
}

is_image_built() {
    local container="$1"
    $RUNTIME images --format '{{.Repository}}' 2>/dev/null | grep -q "${container}"
}

get_container_health() {
    local port="$1"
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/health" 2>/dev/null | grep -q "200"; then
        echo "healthy"
    else
        echo "unhealthy"
    fi
}

get_model_status() {
    local port="$1"
    local api_key="${SAPHENEIA_API_KEY:-default_trading_api_key_please_change}"
    local response
    response=$(curl -s "http://localhost:${port}/forecast/v1/chronos/status" \
        -H "Authorization: Bearer ${api_key}" 2>/dev/null)
    if [[ -n "$response" ]]; then
        echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4
    else
        echo "unknown"
    fi
}

# =============================================================================
# Commands
# =============================================================================

cmd_list() {
    log "${CYAN}"
    cat << 'EOF'
  __  __           _      _   __  __
 |  \/  | ___   __| | ___| | |  \/  | __ _ _ __   __ _  __ _  ___ _ __
 | |\/| |/ _ \ / _` |/ _ \ | | |\/| |/ _` | '_ \ / _` |/ _` |/ _ \ '__|
 | |  | | (_) | (_| |  __/ | | |  | | (_| | | | | (_| | (_| |  __/ |
 |_|  |_|\___/ \__,_|\___|_| |_|  |_|\__,_|_| |_|\__,_|\__, |\___|_|
                                                       |___/
EOF
    log "${NC}"

    log "${BOLD}Container Runtime: ${GREEN}$RUNTIME${NC}"
    log ""

    # Supported models
    log "${BOLD}${GREEN}SUPPORTED MODELS${NC} (implemented in Sapheneia):"
    log "─────────────────────────────────────────────────────────────────────────"
    printf "  ${BOLD}%-20s %-30s %-8s %-10s %-10s${NC}\n" "SLUG" "MODEL_VARIANT" "PORT" "CONTAINER" "STATUS"
    log "─────────────────────────────────────────────────────────────────────────"

    for model in "${MODELS[@]}"; do
        local slug=$(echo "$model" | cut -d'|' -f1)
        local container=$(echo "$model" | cut -d'|' -f2)
        local variant=$(echo "$model" | cut -d'|' -f3)
        local port=$(echo "$model" | cut -d'|' -f4)
        local status=$(echo "$model" | cut -d'|' -f6)

        if [[ "$status" != "supported" ]]; then
            continue
        fi

        local running_status="stopped"
        local health=""

        if is_container_running "$container"; then
            running_status="${GREEN}running${NC}"
            local h=$(get_container_health "$port")
            if [[ "$h" == "healthy" ]]; then
                local m_status=$(get_model_status "$port")
                if [[ "$m_status" == "ready" ]]; then
                    health="${GREEN}ready${NC}"
                elif [[ "$m_status" == "initializing" ]]; then
                    health="${YELLOW}init...${NC}"
                else
                    health="${YELLOW}not init${NC}"
                fi
            else
                health="${RED}unhealthy${NC}"
            fi
        else
            running_status="${RED}stopped${NC}"
            health="-"
        fi

        printf "  %-20s %-30s %-8s %-10b %-10b\n" "$slug" "$variant" "$port" "$running_status" "$health"
    done

    log ""
    log "${BOLD}${YELLOW}PLANNED MODELS${NC} (in AleutianFOSS but no Sapheneia implementation):"
    log "─────────────────────────────────────────────────────────────────────────"

    for model in "${MODELS[@]}"; do
        local slug=$(echo "$model" | cut -d'|' -f1)
        local variant=$(echo "$model" | cut -d'|' -f3)
        local family=$(echo "$model" | cut -d'|' -f5)
        local status=$(echo "$model" | cut -d'|' -f6)

        if [[ "$status" == "supported" ]]; then
            continue
        fi

        printf "  ${YELLOW}%-20s${NC} %-30s (%s)\n" "$slug" "$variant" "$family"
    done

    log ""
    log "${CYAN}To use a model:${NC}"
    log "  1. ${BOLD}./model-manager.sh start chronos-t5-tiny${NC}  # Start container"
    log "  2. ${BOLD}./model-manager.sh init chronos-t5-tiny${NC}   # Initialize model"
    log "  3. ${BOLD}aleutian evaluate run --config ...${NC}         # Run backtest"
    log ""
}

cmd_status() {
    log "${BOLD}Running Forecast Containers:${NC}"
    log ""
    $RUNTIME ps --filter "name=forecast" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
    $RUNTIME ps | grep forecast || echo "No forecast containers running"
    log ""
}

cmd_build() {
    local slug="$1"

    if [[ -z "$slug" ]]; then
        log "${RED}Error: Please specify a model slug${NC}"
        log "Usage: ./model-manager.sh build <slug>"
        exit 1
    fi

    local container=$(get_model_field "$slug" 2)
    local variant=$(get_model_field "$slug" 3)
    local family=$(get_model_field "$slug" 5)
    local status=$(get_model_field "$slug" 6)

    if [[ -z "$container" ]]; then
        log "${RED}Error: Unknown model '$slug'${NC}"
        log "Run './model-manager.sh list' to see available models"
        exit 1
    fi

    if [[ "$status" != "supported" ]]; then
        log "${RED}Error: Model '$slug' is not yet supported in Sapheneia${NC}"
        log "It's defined in AleutianFOSS but needs Sapheneia implementation"
        exit 1
    fi

    log "${CYAN}Building image for: $slug${NC}"
    log "  Container: $container"
    log "  Model: $variant"
    log "  Family: $family"
    log ""

    cd "$SAPHENEIA_DIR"

    # Determine MODEL_NAME based on family
    local model_name="chronos"
    if [[ "$family" == "timesfm" ]]; then
        model_name="timesfm20"
    fi

    $RUNTIME build \
        -t "$container" \
        --build-arg MODEL_NAME="$model_name" \
        --build-arg MODEL_PORT=8000 \
        -f Dockerfile.forecast \
        .

    log ""
    log "${GREEN}Image built successfully: $container${NC}"
}

cmd_start() {
    local slug="$1"

    if [[ "$slug" == "--all" ]]; then
        log "${CYAN}Starting all supported model containers...${NC}"
        for model in "${MODELS[@]}"; do
            local m_slug=$(echo "$model" | cut -d'|' -f1)
            local m_status=$(echo "$model" | cut -d'|' -f6)
            if [[ "$m_status" == "supported" ]]; then
                cmd_start "$m_slug" || true
            fi
        done
        return
    fi

    if [[ -z "$slug" ]]; then
        log "${RED}Error: Please specify a model slug${NC}"
        log "Usage: ./model-manager.sh start <slug>"
        log "       ./model-manager.sh start --all"
        exit 1
    fi

    local container=$(get_model_field "$slug" 2)
    local variant=$(get_model_field "$slug" 3)
    local port=$(get_model_field "$slug" 4)
    local family=$(get_model_field "$slug" 5)
    local status=$(get_model_field "$slug" 6)

    if [[ -z "$container" ]]; then
        log "${RED}Error: Unknown model '$slug'${NC}"
        exit 1
    fi

    if [[ "$status" != "supported" ]]; then
        log "${RED}Error: Model '$slug' is not yet supported${NC}"
        exit 1
    fi

    if is_container_running "$container"; then
        log "${YELLOW}Container $container is already running${NC}"
        return 0
    fi

    log "${CYAN}Starting: $slug${NC}"
    log "  Container: $container"
    log "  Model: $variant"
    log "  Port: $port"

    # Check if image exists, build if not
    if ! is_image_built "$container"; then
        log "  ${YELLOW}Image not found, building...${NC}"
        cmd_build "$slug"
    fi

    cd "$SAPHENEIA_DIR"

    # Ensure network exists
    $RUNTIME network inspect aleutian-shared >/dev/null 2>&1 || \
        $RUNTIME network create aleutian-shared

    # Use podman-compose/docker-compose if available and service exists
    if grep -q "^  ${container}:" "$COMPOSE_FILE" 2>/dev/null; then
        log "  Starting via compose..."
        $COMPOSE_CMD up -d "$container" 2>/dev/null || {
            # Fallback to direct run
            cmd_start_direct "$slug" "$container" "$variant" "$port" "$family"
        }
    else
        # Service not in compose, run directly
        cmd_start_direct "$slug" "$container" "$variant" "$port" "$family"
    fi

    log ""
    log "${GREEN}Container started. Waiting for health check...${NC}"

    # Wait for health
    local attempts=0
    while [[ $attempts -lt 30 ]]; do
        if [[ $(get_container_health "$port") == "healthy" ]]; then
            log "${GREEN}✓ Container is healthy on port $port${NC}"
            log ""
            log "${CYAN}Next step: Initialize the model${NC}"
            log "  ./model-manager.sh init $slug"
            return 0
        fi
        sleep 2
        ((attempts++))
        echo -n "."
    done

    log ""
    log "${YELLOW}Container started but health check not passing yet${NC}"
    log "Check logs: $RUNTIME logs $container"
}

cmd_start_direct() {
    local slug="$1"
    local container="$2"
    local variant="$3"
    local port="$4"
    local family="$5"

    local model_name="chronos"
    if [[ "$family" == "timesfm" ]]; then
        model_name="timesfm20"
    fi

    # Load .env if exists
    local models_cache="${MODELS_CACHE_PATH:-./models_cache}"
    if [[ -f "${SAPHENEIA_DIR}/.env" ]]; then
        source "${SAPHENEIA_DIR}/.env" 2>/dev/null || true
        models_cache="${MODELS_CACHE_PATH:-./models_cache}"
    fi

    $RUNTIME run -d \
        --name "$container" \
        --network aleutian-shared \
        -p "${port}:8000" \
        -e API_HOST=0.0.0.0 \
        -e API_PORT=8000 \
        -e MODEL_NAME="$model_name" \
        -e MODEL_VARIANT="$variant" \
        -e HF_HOME=/models_cache \
        -e DEVICE="${DEVICE:-cpu}" \
        -e PYTHONPATH=/app \
        -e API_SECRET_KEY="${API_SECRET_KEY:-default_trading_api_key_please_change}" \
        -v "${SAPHENEIA_DIR}/forecast:/app/forecast:ro" \
        -v "${SAPHENEIA_DIR}/logs:/app/logs" \
        -v "${models_cache}:/models_cache" \
        "$container"
}

cmd_stop() {
    local slug="$1"

    if [[ "$slug" == "--all" ]]; then
        log "${CYAN}Stopping all forecast containers...${NC}"
        $RUNTIME ps --filter "name=forecast" --format '{{.Names}}' | while read container; do
            log "  Stopping $container..."
            $RUNTIME stop "$container" 2>/dev/null || true
            $RUNTIME rm "$container" 2>/dev/null || true
        done
        log "${GREEN}All forecast containers stopped${NC}"
        return
    fi

    if [[ -z "$slug" ]]; then
        log "${RED}Error: Please specify a model slug${NC}"
        log "Usage: ./model-manager.sh stop <slug>"
        log "       ./model-manager.sh stop --all"
        exit 1
    fi

    local container=$(get_model_field "$slug" 2)

    if [[ -z "$container" ]]; then
        log "${RED}Error: Unknown model '$slug'${NC}"
        exit 1
    fi

    log "${CYAN}Stopping: $container${NC}"
    $RUNTIME stop "$container" 2>/dev/null || true
    $RUNTIME rm "$container" 2>/dev/null || true
    log "${GREEN}Stopped${NC}"
}

cmd_init() {
    local slug="$1"

    if [[ -z "$slug" ]]; then
        log "${RED}Error: Please specify a model slug${NC}"
        log "Usage: ./model-manager.sh init <slug>"
        exit 1
    fi

    local container=$(get_model_field "$slug" 2)
    local variant=$(get_model_field "$slug" 3)
    local port=$(get_model_field "$slug" 4)
    local family=$(get_model_field "$slug" 5)

    if [[ -z "$container" ]]; then
        log "${RED}Error: Unknown model '$slug'${NC}"
        exit 1
    fi

    if ! is_container_running "$container"; then
        log "${RED}Error: Container $container is not running${NC}"
        log "Start it first: ./model-manager.sh start $slug"
        exit 1
    fi

    log "${CYAN}Initializing model: $slug${NC}"
    log "  Container: $container"
    log "  Model: $variant"
    log "  Port: $port"
    log ""

    local api_key="${SAPHENEIA_API_KEY:-default_trading_api_key_please_change}"

    # Determine endpoint based on family
    local init_endpoint="/forecast/v1/chronos/initialization"
    if [[ "$family" == "timesfm" ]]; then
        init_endpoint="/forecast/v1/timesfm20/initialization"
    fi

    log "Sending initialization request..."
    log ""

    local response
    response=$(curl -s -X POST "http://localhost:${port}${init_endpoint}" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${api_key}" \
        -d "{\"model_variant\": \"$variant\"}")

    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"

    log ""

    # Check status
    local status_endpoint="/forecast/v1/chronos/status"
    if [[ "$family" == "timesfm" ]]; then
        status_endpoint="/forecast/v1/timesfm20/status"
    fi

    log "Checking model status..."
    local status_response
    status_response=$(curl -s "http://localhost:${port}${status_endpoint}" \
        -H "Authorization: Bearer ${api_key}")

    if echo "$status_response" | grep -q '"status":"ready"'; then
        log ""
        log "${GREEN}✓ Model initialized and ready!${NC}"
        log ""
        log "${CYAN}You can now run backtests:${NC}"
        log "  aleutian evaluate run --config simulations/strategies/SPY/spy_${slug//-/_}.yaml --api-version unified"
    elif echo "$status_response" | grep -q '"status":"initializing"'; then
        log "${YELLOW}Model is still initializing (downloading weights)...${NC}"
        log "This may take a few minutes for larger models"
        log "Check status: curl http://localhost:${port}${status_endpoint}"
    else
        log "${RED}Model initialization may have failed${NC}"
        log "Response: $status_response"
        log "Check logs: $RUNTIME logs $container"
    fi
}

cmd_pull() {
    local slug="$1"

    if [[ -z "$slug" ]]; then
        log "${RED}Error: Please specify a model slug${NC}"
        log "Usage: ./model-manager.sh pull <slug>"
        exit 1
    fi

    local variant=$(get_model_field "$slug" 3)

    if [[ -z "$variant" ]]; then
        log "${RED}Error: Unknown model '$slug'${NC}"
        exit 1
    fi

    log "${CYAN}Pre-downloading HuggingFace model: $variant${NC}"
    log ""
    log "This will download the model weights to your cache directory."
    log "Models are cached at: ${HF_HOME:-~/.cache/huggingface}"
    log ""

    # Use huggingface-cli if available, otherwise python
    if command -v huggingface-cli &> /dev/null; then
        huggingface-cli download "$variant"
    else
        python3 -c "from huggingface_hub import snapshot_download; snapshot_download('$variant')"
    fi

    log ""
    log "${GREEN}Model downloaded. It will load faster on next initialization.${NC}"
}

cmd_help() {
    cat << EOF
${BOLD}Sapheneia Model Manager${NC}

Manage forecast model containers for backtesting.

${BOLD}USAGE:${NC}
    ./model-manager.sh <command> [options]

${BOLD}COMMANDS:${NC}
    list                    Show all models and their status
    status                  Show running containers
    start <slug|--all>      Start a model container
    stop <slug|--all>       Stop a model container
    init <slug>             Initialize model after container starts
    build <slug>            Build container image
    pull <slug>             Pre-download HuggingFace model weights

${BOLD}SUPPORTED MODELS:${NC}
    ${GREEN}Amazon Chronos T5:${NC}
        chronos-t5-tiny, chronos-t5-mini, chronos-t5-small
        chronos-t5-base, chronos-t5-large

    ${GREEN}Amazon Chronos Bolt:${NC}
        chronos-bolt-mini, chronos-bolt-small, chronos-bolt-base

    ${GREEN}Google TimesFM:${NC}
        timesfm-2-0

${BOLD}EXAMPLES:${NC}
    # Start and initialize Chronos T5 Tiny
    ./model-manager.sh start chronos-t5-tiny
    ./model-manager.sh init chronos-t5-tiny

    # Start all supported models
    ./model-manager.sh start --all

    # Pre-download a large model
    ./model-manager.sh pull chronos-t5-large

${BOLD}ENVIRONMENT:${NC}
    DEVICE                  cpu, cuda, mps (default: cpu)
    MODELS_CACHE_PATH       HuggingFace cache directory
    SAPHENEIA_API_KEY       API key for authentication

EOF
}

# =============================================================================
# Main
# =============================================================================

main() {
    local cmd="${1:-help}"
    shift || true

    case "$cmd" in
        list|ls)
            cmd_list
            ;;
        status|ps)
            cmd_status
            ;;
        start|up)
            cmd_start "$@"
            ;;
        stop|down)
            cmd_stop "$@"
            ;;
        init|initialize)
            cmd_init "$@"
            ;;
        build)
            cmd_build "$@"
            ;;
        pull|download)
            cmd_pull "$@"
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            log "${RED}Unknown command: $cmd${NC}"
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
