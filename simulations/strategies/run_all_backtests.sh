#!/bin/bash
# =============================================================================
# Run All Backtests - Sapheneia Strategy Runner
# =============================================================================
# This script runs all backtest strategies and exports results to CSV.
#
# Usage:
#   ./run_all_backtests.sh              # Run all strategies
#   ./run_all_backtests.sh --ticker SPY # Run only SPY strategies
#   ./run_all_backtests.sh --model tiny # Run only chronos_tiny strategies
#   ./run_all_backtests.sh --dry-run    # Show what would run (no execution)
#
# Requirements:
#   - Sapheneia stack running (forecast, chronos, influxdb)
#   - Environment variables set (ORCHESTRATOR_URL, SAPHENEIA_API_KEY)
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
RESULTS_DIR="${SCRIPT_DIR}/results/$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${RESULTS_DIR}/run_log.txt"

# Default settings
FILTER_TICKER=""
FILTER_MODEL=""
DRY_RUN=false
SKIP_INIT=false

# Counters
TOTAL=0
SUCCESS=0
FAILED=0
SKIPPED=0

# =============================================================================
# Parse Arguments
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --ticker)
            FILTER_TICKER="$2"
            shift 2
            ;;
        --model)
            FILTER_MODEL="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-init)
            SKIP_INIT=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --ticker TICKER   Only run strategies for this ticker (e.g., SPY)"
            echo "  --model MODEL     Only run this model type (tiny, base, bolt, timesfm)"
            echo "  --dry-run         Show what would run without executing"
            echo "  --skip-init       Skip model initialization"
            echo "  --help            Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                        # Run all 104 strategies"
            echo "  $0 --ticker SPY           # Run only SPY (4 strategies)"
            echo "  $0 --model tiny           # Run chronos_tiny for all tickers (26 strategies)"
            echo "  $0 --ticker SPY --model tiny  # Run only SPY with chronos_tiny (1 strategy)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Helper Functions
# =============================================================================

log() {
    local msg="[$(date '+%H:%M:%S')] $1"
    echo -e "$msg"
    [[ -f "$LOG_FILE" ]] && echo "$msg" >> "$LOG_FILE"
}

print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
  ____              _            _
 | __ )  __ _  ___| | _____  __| |_
 |  _ \ / _` |/ __| |/ / _ \/ _` __|
 | |_) | (_| | (__|   <  __/ (_| |_
 |____/ \__,_|\___|_|\_\___|\__,\__|
  Runner - Sapheneia Strategies

EOF
    echo -e "${NC}"
}

check_services() {
    log "${BLUE}Checking services...${NC}"

    local all_ok=true

    # Check Orchestrator
    if curl -s http://localhost:12700/health > /dev/null 2>&1; then
        log "  ${GREEN}✓${NC} Sapheneia Orchestrator (12700)"
    else
        log "  ${RED}✗${NC} Sapheneia Orchestrator (12700) - NOT RUNNING"
        all_ok=false
    fi

    # Check Chronos
    if curl -s http://localhost:12710/health > /dev/null 2>&1; then
        log "  ${GREEN}✓${NC} Chronos Forecast (12710)"
    else
        log "  ${RED}✗${NC} Chronos Forecast (12710) - NOT RUNNING"
        all_ok=false
    fi

    # Check InfluxDB
    if curl -s http://localhost:12130/health > /dev/null 2>&1; then
        log "  ${GREEN}✓${NC} InfluxDB (12130)"
    else
        log "  ${RED}✗${NC} InfluxDB (12130) - NOT RUNNING"
        all_ok=false
    fi

    if [[ "$all_ok" != true ]]; then
        log ""
        log "${RED}ERROR: Required services are not running.${NC}"
        log "Start the stack with: ./scripts/start-stack.sh"
        exit 1
    fi

    log ""
}

initialize_models() {
    if [[ "$SKIP_INIT" == true ]]; then
        log "${YELLOW}Skipping model initialization (--skip-init)${NC}"
        return
    fi

    log "${BLUE}Initializing forecast models...${NC}"

    # Initialize Chronos
    log "  Initializing Chronos T5-Tiny..."
    local response
    response=$(curl -s -X POST http://localhost:12710/forecast/v1/chronos/initialization \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${SAPHENEIA_API_KEY:-default_trading_api_key_please_change}" \
        -d '{}')

    if echo "$response" | grep -q "ready\|initialized"; then
        log "  ${GREEN}✓${NC} Chronos model ready"
    else
        log "  ${YELLOW}⚠${NC} Chronos initialization response: $response"
    fi

    log ""
}

run_strategy() {
    local strategy_file="$1"
    local strategy_name=$(basename "$strategy_file" .yaml)
    local ticker=$(basename "$(dirname "$strategy_file")")

    ((TOTAL++))

    # Apply filters
    if [[ -n "$FILTER_TICKER" ]] && [[ "$ticker" != "$FILTER_TICKER" ]]; then
        ((SKIPPED++))
        return
    fi

    if [[ -n "$FILTER_MODEL" ]] && [[ "$strategy_name" != *"$FILTER_MODEL"* ]]; then
        ((SKIPPED++))
        return
    fi

    log "${CYAN}[$TOTAL] Running: ${ticker}/${strategy_name}${NC}"

    if [[ "$DRY_RUN" == true ]]; then
        log "  ${YELLOW}[DRY RUN] Would execute: aleutian evaluate run --config $strategy_file${NC}"
        ((SUCCESS++))
        return
    fi

    # Run the backtest and capture output
    local output
    local start_time=$(date +%s)

    output=$(aleutian evaluate run \
        --config "$strategy_file" \
        --api-version unified 2>&1) || true

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Extract Run ID
    local run_id
    run_id=$(echo "$output" | grep "Run ID:" | awk '{print $NF}' | tail -1)

    if [[ -z "$run_id" ]]; then
        log "  ${RED}✗ Failed - no Run ID generated${NC}"
        log "  Output: $(echo "$output" | tail -3)"
        ((FAILED++))
        return
    fi

    log "  ${GREEN}✓${NC} Completed in ${duration}s - Run ID: ${run_id}"

    # Export results
    log "  Exporting to CSV..."
    local export_output
    export_output=$(aleutian evaluate export "$run_id" 2>&1) || true

    if echo "$export_output" | grep -q "Export complete"; then
        # Move CSV to results directory
        local csv_file="backtest_${run_id}.csv"
        if [[ -f "$csv_file" ]]; then
            mv "$csv_file" "${RESULTS_DIR}/"
            log "  ${GREEN}✓${NC} Saved: ${RESULTS_DIR}/${csv_file}"
        fi
        ((SUCCESS++))
    else
        log "  ${YELLOW}⚠${NC} Export issue: $(echo "$export_output" | tail -1)"
        ((SUCCESS++))  # Still count as success if backtest ran
    fi

    log ""
}

print_summary() {
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    local minutes=$((total_duration / 60))
    local seconds=$((total_duration % 60))

    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}                      SUMMARY                              ${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Total strategies:  ${BOLD}$TOTAL${NC}"
    echo -e "  Successful:        ${GREEN}$SUCCESS${NC}"
    echo -e "  Failed:            ${RED}$FAILED${NC}"
    echo -e "  Skipped:           ${YELLOW}$SKIPPED${NC}"
    echo ""
    echo -e "  Duration:          ${minutes}m ${seconds}s"
    echo -e "  Results saved to:  ${BOLD}${RESULTS_DIR}/${NC}"
    echo ""

    if [[ $SUCCESS -gt 0 ]]; then
        echo -e "${CYAN}CSV files generated:${NC}"
        ls -1 "${RESULTS_DIR}"/*.csv 2>/dev/null | head -10
        local csv_count=$(ls -1 "${RESULTS_DIR}"/*.csv 2>/dev/null | wc -l)
        if [[ $csv_count -gt 10 ]]; then
            echo "  ... and $((csv_count - 10)) more"
        fi
        echo ""
    fi

    # Save summary to log
    {
        echo ""
        echo "=== SUMMARY ==="
        echo "Total: $TOTAL | Success: $SUCCESS | Failed: $FAILED | Skipped: $SKIPPED"
        echo "Duration: ${minutes}m ${seconds}s"
    } >> "$LOG_FILE"

    echo -e "${GREEN}Done! Check ${RESULTS_DIR}/ for all CSV results.${NC}"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    START_TIME=$(date +%s)

    print_banner

    # Set environment variables if not set
    export ORCHESTRATOR_URL="${ORCHESTRATOR_URL:-http://localhost:12700}"
    export SAPHENEIA_API_KEY="${SAPHENEIA_API_KEY:-default_trading_api_key_please_change}"

    # Show configuration
    log "${BOLD}Configuration:${NC}"
    log "  Orchestrator URL: $ORCHESTRATOR_URL"
    log "  Results directory: $RESULTS_DIR"
    [[ -n "$FILTER_TICKER" ]] && log "  Filter ticker: $FILTER_TICKER"
    [[ -n "$FILTER_MODEL" ]] && log "  Filter model: $FILTER_MODEL"
    [[ "$DRY_RUN" == true ]] && log "  ${YELLOW}DRY RUN MODE${NC}"
    log ""

    # Create results directory
    mkdir -p "$RESULTS_DIR"
    touch "$LOG_FILE"
    log "Log file: $LOG_FILE"
    log ""

    # Pre-flight checks
    if [[ "$DRY_RUN" != true ]]; then
        check_services
        initialize_models
    fi

    # Count strategies
    local strategy_count
    if [[ -n "$FILTER_TICKER" ]]; then
        strategy_count=$(find "${SCRIPT_DIR}/${FILTER_TICKER}" -name "*.yaml" 2>/dev/null | wc -l)
    else
        strategy_count=$(find "${SCRIPT_DIR}" -mindepth 2 -name "*.yaml" | wc -l)
    fi

    log "${BOLD}Found $strategy_count strategy files to process${NC}"
    log ""

    # Process each strategy
    if [[ -n "$FILTER_TICKER" ]]; then
        # Run specific ticker
        for strategy in "${SCRIPT_DIR}/${FILTER_TICKER}"/*.yaml; do
            [[ -f "$strategy" ]] && run_strategy "$strategy"
        done
    else
        # Run all tickers
        for ticker_dir in "${SCRIPT_DIR}"/*/; do
            # Skip non-directories and results folder
            [[ ! -d "$ticker_dir" ]] && continue
            [[ "$(basename "$ticker_dir")" == "results" ]] && continue

            for strategy in "${ticker_dir}"*.yaml; do
                [[ -f "$strategy" ]] && run_strategy "$strategy"
            done
        done
    fi

    print_summary
}

# Run main
main "$@"
