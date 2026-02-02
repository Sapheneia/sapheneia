#!/bin/bash
# =============================================================================
# Run All Backtests - Sapheneia Strategy Runner
# =============================================================================
# This script runs all backtest strategies and exports results to CSV.
#
# Usage:
#   ./run_all_backtests.sh              # Run all strategies (auto-fetches missing data)
#   ./run_all_backtests.sh --ticker SPY # Run only SPY strategies
#   ./run_all_backtests.sh --model tiny # Run only chronos_tiny strategies
#   ./run_all_backtests.sh --dry-run    # Show what would run (no execution)
#   ./run_all_backtests.sh --skip-fetch # Skip data fetching (assumes data exists)
#
# Requirements:
#   - Sapheneia stack running (forecast, chronos, influxdb)
#   - Environment variables set (ORCHESTRATOR_URL, SAPHENEIA_API_KEY)
#
# Auto Data Fetch:
#   By default, the script checks InfluxDB for each ticker and fetches
#   missing data using 'aleutian timeseries fetch'. Use --skip-fetch to disable.
# =============================================================================

# Don't use set -e - handle errors explicitly for better control
# set -e

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
SKIP_FETCH=false
USE_SAPHENEIA=false  # Use Python CLI instead of Go CLI

# Track which tickers we've already fetched data for
declare -A FETCHED_TICKERS

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
        --skip-fetch)
            SKIP_FETCH=true
            shift
            ;;
        --sapheneia|--python)
            USE_SAPHENEIA=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --ticker TICKER   Only run strategies for this ticker (e.g., SPY)"
            echo "  --model MODEL     Only run this model (e.g., chronos-t5-tiny, chronos-bolt-mini, timesfm)"
            echo "  --dry-run         Show what would run without executing"
            echo "  --skip-init       Skip model initialization"
            echo "  --skip-fetch      Skip automatic data fetching (assumes data exists)"
            echo "  --sapheneia       Use Python sapheneia CLI instead of Go aleutian CLI"
            echo "  --help            Show this help"
            echo ""
            echo "Models:"
            echo "  chronos-t5-tiny, chronos-t5-base, chronos-bolt-mini, timesfm"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Run all strategies"
            echo "  $0 --ticker SPY                       # Run only SPY (4 strategies)"
            echo "  $0 --model chronos-t5-tiny            # Run chronos-t5-tiny for all tickers"
            echo "  $0 --ticker SPY --model chronos-t5-tiny  # Run only SPY with chronos-t5-tiny"
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
    if [[ -f "$LOG_FILE" ]]; then
        echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
    fi
}

print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
  ____              _                   _
 / ___|  __ _ _ __ | |__   ___ _ __   ___(_) __ _
 \___ \ / _` | '_ \| '_ \ / _ \ '_ \ / _ \ |/ _` |
  ___) | (_| | |_) | | | |  __/ | | |  __/ | (_| |
 |____/ \__,_| .__/|_| |_|\___|_| |_|\___|_|\__,_|
             |_|
  Backtest Runner - Time Series Forecasting

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

# Convert model slug to filename pattern
# Maps AleutianFOSS model slugs to strategy filename patterns
normalize_model_filter() {
    local model="$1"
    case "$model" in
        # --- AMAZON CHRONOS T5 ---
        chronos-t5-tiny)    echo "chronos-t5-tiny" ;;
        chronos-t5-mini)    echo "chronos-t5-mini" ;;
        chronos-t5-small)   echo "chronos-t5-small" ;;
        chronos-t5-base)    echo "chronos-t5-base" ;;
        chronos-t5-large)   echo "chronos-t5-large" ;;

        # --- AMAZON CHRONOS BOLT ---
        chronos-bolt-mini)  echo "chronos-bolt-mini" ;;
        chronos-bolt-small) echo "chronos-bolt-small" ;;
        chronos-bolt-base)  echo "chronos-bolt-base" ;;

        # --- GOOGLE TIMESFM ---
        timesfm-1-0)        echo "timesfm-1-0" ;;
        timesfm-2-0|timesfm) echo "timesfm-2-0" ;;
        timesfm-2-5)        echo "timesfm-2-5" ;;

        # --- SALESFORCE MOIRAI ---
        moirai-1-0-small)   echo "moirai-1-0-small" ;;
        moirai-1-1-small)   echo "moirai-1-1-small" ;;
        moirai-1-1-base)    echo "moirai-1-1-base" ;;
        moirai-1-1-large)   echo "moirai-1-1-large" ;;
        moirai-2-0-small)   echo "moirai-2-0-small" ;;

        # --- IBM GRANITE ---
        granite-ttm-r1)     echo "granite-ttm-r1" ;;
        granite-ttm-r2)     echo "granite-ttm-r2" ;;
        granite-flowstate)  echo "granite-flowstate" ;;
        granite-patchtsmixer) echo "granite-patchtsmixer" ;;
        granite-patchtst)   echo "granite-patchtst" ;;

        # --- AUTONLAB MOMENT ---
        moment-small)       echo "moment-small" ;;
        moment-base)        echo "moment-base" ;;
        moment-large)       echo "moment-large" ;;

        # --- ALIBABA YINGLONG ---
        yinglong-6m)        echo "yinglong-6m" ;;
        yinglong-50m)       echo "yinglong-50m" ;;
        yinglong-110m)      echo "yinglong-110m" ;;
        yinglong-300m)      echo "yinglong-300m" ;;

        # --- MISC / SINGLE MODELS ---
        lag-llama)          echo "lag-llama" ;;
        kairos-10m)         echo "kairos-10m" ;;
        kairos-50m)         echo "kairos-50m" ;;
        timemoe-200m)       echo "timemoe-200m" ;;
        timer)              echo "timer" ;;
        sundial)            echo "sundial" ;;
        toto)               echo "toto" ;;
        falcon-tst)         echo "falcon-tst" ;;
        tempopfn)           echo "tempopfn" ;;
        forecastpfn)        echo "forecastpfn" ;;
        chattime)           echo "chattime" ;;
        opencity)           echo "opencity" ;;
        units)              echo "units" ;;

        *)
            # Pass through as-is for direct filename matching
            echo "$model"
            ;;
    esac
}

# Parse date from YAML (YYYYMMDD format) and convert to ISO format
parse_yaml_date() {
    local yaml_file="$1"
    local field="$2"
    local date_str
    date_str=$(grep "^  ${field}:" "$yaml_file" | sed 's/.*: *"//' | sed 's/".*//' | tr -d ' ')
    if [[ -n "$date_str" && ${#date_str} -eq 8 ]]; then
        # Convert YYYYMMDD to YYYY-MM-DD
        echo "${date_str:0:4}-${date_str:4:2}-${date_str:6:2}"
    fi
}

# Calculate days between two dates (YYYY-MM-DD format)
days_between() {
    local start="$1"
    local end="$2"
    local start_sec end_sec
    start_sec=$(date -d "$start" +%s 2>/dev/null) || start_sec=$(date -j -f "%Y-%m-%d" "$start" +%s 2>/dev/null)
    end_sec=$(date -d "$end" +%s 2>/dev/null) || end_sec=$(date -j -f "%Y-%m-%d" "$end" +%s 2>/dev/null)
    echo $(( (end_sec - start_sec) / 86400 ))
}

# Check if ticker data exists in InfluxDB, fetch if missing
ensure_ticker_data() {
    local ticker="$1"
    local strategy_file="$2"

    # Skip if we already checked this ticker with sufficient data
    if [[ -n "${FETCHED_TICKERS[$ticker]:-}" ]]; then
        return 0
    fi

    if [[ "$SKIP_FETCH" == true ]]; then
        return 0
    fi

    if [[ "$DRY_RUN" == true ]]; then
        log "  ${YELLOW}[DRY RUN] Would check/fetch data for ${ticker}${NC}"
        FETCHED_TICKERS[$ticker]=1
        return 0
    fi

    # Parse dates from the strategy YAML
    local fetch_start_date start_date end_date
    fetch_start_date=$(parse_yaml_date "$strategy_file" "fetch_start_date")
    start_date=$(parse_yaml_date "$strategy_file" "start_date")
    end_date=$(parse_yaml_date "$strategy_file" "end_date")

    # Fallback if fetch_start_date not specified: use start_date
    if [[ -z "$fetch_start_date" ]]; then
        fetch_start_date="$start_date"
    fi

    if [[ -z "$fetch_start_date" || -z "$end_date" ]]; then
        log "  ${YELLOW}⚠ Could not parse dates from YAML, skipping data check${NC}"
        FETCHED_TICKERS[$ticker]=1
        return 0
    fi

    # Calculate required days: from fetch_start_date to end_date
    local required_days
    required_days=$(days_between "$fetch_start_date" "$end_date")

    # Query InfluxDB to check if data exists for the required range
    local influx_url="${INFLUXDB_URL:-http://localhost:12130}"
    local influx_token="${INFLUXDB_TOKEN:-your_super_secret_admin_token}"
    local influx_org="${INFLUXDB_ORG:-aleutian-finance}"
    local influx_bucket="${INFLUXDB_BUCKET:-financial-data}"

    # Check if we have data for this ticker in the required date range
    local query="from(bucket: \"${influx_bucket}\")
        |> range(start: ${fetch_start_date}T00:00:00Z, stop: ${end_date}T23:59:59Z)
        |> filter(fn: (r) => r[\"ticker\"] == \"${ticker}\")
        |> filter(fn: (r) => r[\"_field\"] == \"close\")
        |> count()"

    local response
    response=$(curl -s -X POST "${influx_url}/api/v2/query?org=${influx_org}" \
        -H "Authorization: Token ${influx_token}" \
        -H "Content-Type: application/vnd.flux" \
        -d "$query" 2>/dev/null)

    # Check if we got data (response contains count > 0)
    local count=0
    if echo "$response" | grep -q "_value"; then
        count=$(echo "$response" | grep -oP '(?<=,)[0-9]+(?=\r?$)' | tail -1 2>/dev/null)
        count=${count:-0}
    fi

    # Estimate expected trading days (~252 per year, so ~70% of calendar days)
    local expected_trading_days=$(( required_days * 70 / 100 ))
    local min_required=$(( expected_trading_days * 80 / 100 ))  # Need at least 80% of expected

    if [[ "$count" -lt "$min_required" ]]; then
        log "  ${YELLOW}Fetching data for ${ticker} (have ${count}, need ~${min_required})...${NC}"

        # Add buffer days for safety
        local fetch_days=$(( required_days + 30 ))

        # Use aleutian to fetch the data
        local fetch_output
        fetch_output=$(aleutian timeseries fetch "$ticker" --days "$fetch_days" 2>&1) || true

        if echo "$fetch_output" | grep -qi "error\|failed"; then
            log "  ${RED}⚠ Failed to fetch data for ${ticker}${NC}"
            log "    $(echo "$fetch_output" | tail -1)"
        else
            log "  ${GREEN}✓${NC} Data fetched for ${ticker}"
        fi
    fi

    # Mark as checked so we don't try again
    FETCHED_TICKERS[$ticker]=1
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

    if [[ -n "$FILTER_MODEL" ]]; then
        local normalized_filter
        normalized_filter=$(normalize_model_filter "$FILTER_MODEL")
        if [[ "$strategy_name" != *"$normalized_filter"* ]]; then
            ((SKIPPED++))
            return
        fi
    fi

    log "${CYAN}[$TOTAL] Running: ${ticker}/${strategy_name}${NC}"

    # Ensure we have data for this ticker (auto-fetch if missing)
    ensure_ticker_data "$ticker" "$strategy_file"

    if [[ "$DRY_RUN" == true ]]; then
        if [[ "$USE_SAPHENEIA" == true ]]; then
            log "  ${YELLOW}[DRY RUN] Would execute: sapheneia evaluate --config $strategy_file${NC}"
        else
            log "  ${YELLOW}[DRY RUN] Would execute: aleutian evaluate run --config $strategy_file${NC}"
        fi
        ((SUCCESS++))
        return
    fi

    # Run the backtest and capture output
    local output
    local start_time=$(date +%s)

    if [[ "$USE_SAPHENEIA" == true ]]; then
        # Use Python sapheneia CLI
        output=$(sapheneia evaluate \
            --config "$strategy_file" \
            --output "${RESULTS_DIR}" 2>&1) || true
    else
        # Use Go aleutian CLI
        output=$(aleutian evaluate run \
            --config "$strategy_file" \
            --api-version unified 2>&1) || true
    fi

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
    if [[ "$USE_SAPHENEIA" == true ]]; then
        log "  CLI: ${GREEN}sapheneia (Python)${NC}"
    else
        log "  CLI: aleutian (Go)"
    fi
    [[ -n "$FILTER_TICKER" ]] && log "  Filter ticker: $FILTER_TICKER"
    [[ -n "$FILTER_MODEL" ]] && log "  Filter model: $FILTER_MODEL"
    [[ "$DRY_RUN" == true ]] && log "  ${YELLOW}DRY RUN MODE${NC}"
    [[ "$SKIP_FETCH" == true ]] && log "  ${YELLOW}Skip data fetch: enabled${NC}"
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
