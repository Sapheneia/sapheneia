#!/bin/bash
# =============================================================================
# Model Test Suite - Sapheneia Forecast Models
# =============================================================================
# Systematic testing of all forecast models to determine working status.
#
# Usage:
#   ./test-models.sh                    # Test all models
#   ./test-models.sh --quick            # Test only known-working models
#   ./test-models.sh --model chronos-t5-tiny  # Test specific model
#   ./test-models.sh --family chronos   # Test all models in a family
#   ./test-models.sh --report           # Show last test report
#
# Test Levels:
#   1. Container starts (health check passes)
#   2. Model initializes (API returns ready)
#   3. Inference works (forecast returns valid data)
#   4. Backtest works (aleutian evaluate run succeeds)
# =============================================================================

set -o pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAPHENEIA_DIR="$(dirname "$SCRIPT_DIR")"
REPORT_FILE="${SAPHENEIA_DIR}/test_results/model_test_report_$(date +%Y%m%d_%H%M%S).md"
SUMMARY_FILE="${SAPHENEIA_DIR}/test_results/MODEL_STATUS.md"

# Detect container runtime
if command -v podman &> /dev/null; then
    RUNTIME="podman"
    COMPOSE_CMD="podman-compose"
else
    RUNTIME="docker"
    COMPOSE_CMD="docker-compose"
fi

# API Key
API_KEY="${SAPHENEIA_API_KEY:-default_trading_api_key_please_change}"

# =============================================================================
# Model Registry with Known Status
# =============================================================================
# Format: "slug|hf_id|port|family|known_status|notes"
# known_status: working, untested, broken, not_implemented

declare -a MODELS=(
    # === AMAZON CHRONOS T5 ===
    "chronos-t5-tiny|amazon/chronos-t5-tiny|12710|chronos|working|Verified working"
    "chronos-t5-mini|amazon/chronos-t5-mini|12711|chronos|working|Verified working"
    "chronos-t5-small|amazon/chronos-t5-small|12712|chronos|untested|Needs testing"
    "chronos-t5-base|amazon/chronos-t5-base|12713|chronos|working|Verified working"
    "chronos-t5-large|amazon/chronos-t5-large|12714|chronos|working|Verified working"

    # === AMAZON CHRONOS BOLT ===
    "chronos-bolt-mini|amazon/chronos-bolt-mini|12715|chronos|untested|May have ChronosPipeline compatibility issues"
    "chronos-bolt-small|amazon/chronos-bolt-small|12716|chronos|untested|May have ChronosPipeline compatibility issues"
    "chronos-bolt-base|amazon/chronos-bolt-base|12717|chronos|untested|May have ChronosPipeline compatibility issues"

    # === GOOGLE TIMESFM ===
    "timesfm-1-0|google/timesfm-1.0-200m|12720|timesfm|not_implemented|No Sapheneia container"
    "timesfm-2-0|google/timesfm-2.0-500m-pytorch|12721|timesfm|working|Verified working"
    "timesfm-2-5|google/timesfm-2.5|12722|timesfm|not_implemented|No Sapheneia container"

    # === SALESFORCE MOIRAI ===
    "moirai-1-0-small|Salesforce/moirai-1.0-R-small|12730|moirai|not_implemented|No Sapheneia impl"
    "moirai-1-1-small|Salesforce/moirai-1.1-R-small|12731|moirai|not_implemented|No Sapheneia impl"
    "moirai-1-1-base|Salesforce/moirai-1.1-R-base|12732|moirai|not_implemented|No Sapheneia impl"
    "moirai-1-1-large|Salesforce/moirai-1.1-R-large|12733|moirai|not_implemented|No Sapheneia impl"
    "moirai-2-0-small|Salesforce/moirai-2.0-R-small|12734|moirai|not_implemented|No Sapheneia impl"

    # === IBM GRANITE ===
    "granite-ttm-r1|ibm/granite-timeseries-ttm-r1|12740|granite|not_implemented|No Sapheneia impl"
    "granite-ttm-r2|ibm/granite-timeseries-ttm-r2|12741|granite|not_implemented|No Sapheneia impl"
    "granite-flowstate|ibm-granite/granite-timeseries-flowstate|12742|granite|not_implemented|No Sapheneia impl"
    "granite-patchtsmixer|ibm-granite/granite-timeseries-patchtsmixer|12743|granite|not_implemented|No Sapheneia impl"
    "granite-patchtst|ibm-granite/granite-timeseries-patchtst|12744|granite|not_implemented|No Sapheneia impl"

    # === AUTONLAB MOMENT ===
    "moment-small|AutonLab/MOMENT-1-small|12750|moment|not_implemented|No Sapheneia impl"
    "moment-base|AutonLab/MOMENT-1-base|12751|moment|not_implemented|No Sapheneia impl"
    "moment-large|AutonLab/MOMENT-1-large|12752|moment|not_implemented|No Sapheneia impl"

    # === ALIBABA YINGLONG ===
    "yinglong-6m|Alibaba/yinglong-6m|12760|yinglong|not_implemented|No Sapheneia impl"
    "yinglong-50m|Alibaba/yinglong-50m|12761|yinglong|not_implemented|No Sapheneia impl"
    "yinglong-110m|Alibaba/yinglong-110m|12762|yinglong|not_implemented|No Sapheneia impl"
    "yinglong-300m|Alibaba/yinglong-300m|12763|yinglong|not_implemented|No Sapheneia impl"

    # === MISC MODELS ===
    "lag-llama|time-series-foundation-models/Lag-Llama|12770|lagllama|not_implemented|No Sapheneia impl"
    "kairos-10m|Salesforce/kairos-10m|12771|kairos|not_implemented|No Sapheneia impl"
    "kairos-50m|Salesforce/kairos-50m|12772|kairos|not_implemented|No Sapheneia impl"
    "timemoe-200m|Maple728/TimeMoE-200M|12773|timemoe|not_implemented|No Sapheneia impl"
    "timer|thuml/Timer|12774|timer|not_implemented|No Sapheneia impl"
    "sundial|Sundial/sundial|12775|sundial|not_implemented|No Sapheneia impl"
    "toto|Databricks/toto|12776|toto|not_implemented|No Sapheneia impl"
    "falcon-tst|tii-falcon/falcon-tst|12777|falcon|not_implemented|No Sapheneia impl"
    "tempopfn|Salesforce/TempoPFN|12778|tempopfn|not_implemented|No Sapheneia impl"
    "forecastpfn|amazon/forecastpfn|12779|forecastpfn|not_implemented|No Sapheneia impl"
    "chattime|amazon/chattime|12780|chattime|not_implemented|No Sapheneia impl"
    "opencity|OpenCity/opencity|12781|opencity|not_implemented|No Sapheneia impl"
    "units|mzchen/UniTS|12782|units|not_implemented|No Sapheneia impl"
)

# Test results (populated during testing)
declare -A TEST_RESULTS

# =============================================================================
# Helper Functions
# =============================================================================

log() { echo -e "$1"; }

get_field() {
    local model="$1"
    local field="$2"
    echo "$model" | cut -d'|' -f"$field"
}

find_model() {
    local slug="$1"
    for model in "${MODELS[@]}"; do
        if [[ "$(get_field "$model" 1)" == "$slug" ]]; then
            echo "$model"
            return 0
        fi
    done
    return 1
}

# =============================================================================
# Test Functions
# =============================================================================

# Test 1: Can container start and pass health check?
test_container_health() {
    local slug="$1"
    local port="$2"

    # Check if already running
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/health" 2>/dev/null | grep -q "200"; then
        return 0
    fi
    return 1
}

# Test 2: Can model initialize?
test_model_init() {
    local slug="$1"
    local port="$2"
    local hf_id="$3"
    local family="$4"

    local init_endpoint="/forecast/v1/chronos/initialization"
    if [[ "$family" == "timesfm" ]]; then
        init_endpoint="/forecast/v1/timesfm20/initialization"
    fi

    # Try to initialize
    local response
    response=$(curl -s -X POST "http://localhost:${port}${init_endpoint}" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${API_KEY}" \
        -d "{\"model_variant\": \"$hf_id\"}" 2>/dev/null)

    if echo "$response" | grep -qi "ready\|initialized\|already"; then
        return 0
    fi
    return 1
}

# Test 3: Can model return status as ready?
test_model_status() {
    local slug="$1"
    local port="$2"
    local family="$3"

    local status_endpoint="/forecast/v1/chronos/status"
    if [[ "$family" == "timesfm" ]]; then
        status_endpoint="/forecast/v1/timesfm20/status"
    fi

    local response
    response=$(curl -s "http://localhost:${port}${status_endpoint}" \
        -H "Authorization: Bearer ${API_KEY}" 2>/dev/null)

    if echo "$response" | grep -qi '"ready"'; then
        return 0
    fi
    return 1
}

# Test 4: Can model perform inference?
test_inference() {
    local slug="$1"
    local port="$2"
    local family="$3"

    # Simple test data
    local test_data='[100.0, 101.5, 99.8, 102.3, 103.1, 101.9, 104.2, 103.8, 105.1, 104.5]'

    local response
    response=$(curl -s -X POST "http://localhost:${port}/forecast/v1/inference" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${API_KEY}" \
        -d "{\"context\": ${test_data}, \"prediction_length\": 5}" 2>/dev/null)

    if echo "$response" | grep -qi "forecast\|prediction\|values"; then
        return 0
    fi
    return 1
}

# Test 5: Can run full backtest and export CSV?
test_backtest() {
    local slug="$1"
    local ticker="${2:-SPY}"

    # Find the strategy file
    local strategy_file="${SAPHENEIA_DIR}/simulations/strategies/${ticker}/${ticker,,}_${slug//-/_}.yaml"

    if [[ ! -f "$strategy_file" ]]; then
        log "    Strategy file not found: $strategy_file"
        return 1
    fi

    # Run the backtest
    local output
    output=$(aleutian evaluate run --config "$strategy_file" --api-version unified 2>&1) || true

    # Extract Run ID
    local run_id
    run_id=$(echo "$output" | grep "Run ID:" | awk '{print $NF}' | tail -1)

    if [[ -z "$run_id" ]]; then
        log "    No Run ID generated"
        log "    Output: $(echo "$output" | tail -2)"
        return 1
    fi

    log "    Run ID: $run_id"

    # Export to CSV
    local export_output
    export_output=$(aleutian evaluate export "$run_id" 2>&1) || true

    if echo "$export_output" | grep -q "Export complete"; then
        # Move CSV to test_results
        local csv_file="backtest_${run_id}.csv"
        if [[ -f "$csv_file" ]]; then
            mv "$csv_file" "${SAPHENEIA_DIR}/test_results/"
            log "    CSV: test_results/${csv_file}"
            return 0
        fi
    fi

    log "    Export failed: $(echo "$export_output" | tail -1)"
    return 1
}

# Full test suite for a single model
# Args: slug [include_backtest] [ticker]
run_model_test() {
    local slug="$1"
    local include_backtest="${2:-false}"
    local ticker="${3:-SPY}"

    local model_entry
    model_entry=$(find_model "$slug")

    if [[ -z "$model_entry" ]]; then
        log "${RED}Unknown model: $slug${NC}"
        return 1
    fi

    local hf_id=$(get_field "$model_entry" 2)
    local port=$(get_field "$model_entry" 3)
    local family=$(get_field "$model_entry" 4)
    local known_status=$(get_field "$model_entry" 5)
    local notes=$(get_field "$model_entry" 6)

    local total_tests=4
    [[ "$include_backtest" == "true" ]] && total_tests=5

    log ""
    log "${CYAN}Testing: ${BOLD}$slug${NC}"
    log "  HuggingFace: $hf_id"
    log "  Port: $port | Family: $family"
    log "  Known status: $known_status"
    [[ -n "$notes" ]] && log "  Notes: $notes"
    log ""

    local result="not_tested"
    local details=""

    # Test 1: Health check
    log -n "  [1/${total_tests}] Container health check... "
    if test_container_health "$slug" "$port"; then
        log "${GREEN}PASS${NC}"
    else
        log "${RED}FAIL${NC} (container not running or unhealthy)"
        result="container_failed"
        details="Container not running on port $port"
        TEST_RESULTS[$slug]="$result|$details"
        return 1
    fi

    # Test 2: Model initialization
    log -n "  [2/${total_tests}] Model initialization... "
    if test_model_init "$slug" "$port" "$hf_id" "$family"; then
        log "${GREEN}PASS${NC}"
    else
        log "${RED}FAIL${NC} (initialization failed)"
        result="init_failed"
        details="Model failed to initialize"
        TEST_RESULTS[$slug]="$result|$details"
        return 1
    fi

    # Test 3: Model status
    log -n "  [3/${total_tests}] Model status ready... "
    # Wait a moment for initialization to complete
    sleep 2
    if test_model_status "$slug" "$port" "$family"; then
        log "${GREEN}PASS${NC}"
    else
        log "${YELLOW}WAIT${NC} (model may still be loading)"
        # Try again after longer wait
        sleep 10
        if test_model_status "$slug" "$port" "$family"; then
            log "  [3/${total_tests}] Model status ready... ${GREEN}PASS${NC} (after wait)"
        else
            log "  [3/${total_tests}] Model status ready... ${RED}FAIL${NC}"
            result="status_not_ready"
            details="Model did not reach ready status"
            TEST_RESULTS[$slug]="$result|$details"
            return 1
        fi
    fi

    # Test 4: Inference
    log -n "  [4/${total_tests}] Inference test... "
    if test_inference "$slug" "$port" "$family"; then
        log "${GREEN}PASS${NC}"
        result="working"
        details="Inference passed"
    else
        log "${RED}FAIL${NC} (inference returned invalid response)"
        result="inference_failed"
        details="Inference did not return valid forecast"
        TEST_RESULTS[$slug]="$result|$details"
        return 1
    fi

    # Test 5: Full backtest with CSV export (optional)
    if [[ "$include_backtest" == "true" ]]; then
        log -n "  [5/${total_tests}] Full backtest (${ticker})... "
        if test_backtest "$slug" "$ticker"; then
            log "${GREEN}PASS${NC}"
            result="working_full"
            details="All tests passed including backtest"
        else
            log "${RED}FAIL${NC}"
            result="backtest_failed"
            details="Backtest or CSV export failed"
            TEST_RESULTS[$slug]="$result|$details"
            return 1
        fi
    fi

    TEST_RESULTS[$slug]="$result|$details"

    if [[ "$result" == "working" || "$result" == "working_full" ]]; then
        log "  ${GREEN}>>> MODEL WORKING <<<${NC}"
        return 0
    else
        return 1
    fi
}

# =============================================================================
# Report Generation
# =============================================================================

generate_report() {
    mkdir -p "$(dirname "$REPORT_FILE")"

    local working=0
    local untested=0
    local broken=0
    local not_impl=0

    {
        echo "# Model Test Report"
        echo ""
        echo "Generated: $(date)"
        echo ""
        echo "## Summary"
        echo ""
        echo "| Status | Count |"
        echo "|--------|-------|"
    } > "$REPORT_FILE"

    # Count by status
    for model in "${MODELS[@]}"; do
        local status=$(get_field "$model" 5)
        case "$status" in
            working) ((working++)) ;;
            untested) ((untested++)) ;;
            broken) ((broken++)) ;;
            not_implemented) ((not_impl++)) ;;
        esac
    done

    {
        echo "| Working | $working |"
        echo "| Untested | $untested |"
        echo "| Broken | $broken |"
        echo "| Not Implemented | $not_impl |"
        echo "| **Total** | **${#MODELS[@]}** |"
        echo ""
        echo "## Working Models"
        echo ""
        echo "| Model | HuggingFace ID | Family |"
        echo "|-------|----------------|--------|"
    } >> "$REPORT_FILE"

    for model in "${MODELS[@]}"; do
        local slug=$(get_field "$model" 1)
        local hf_id=$(get_field "$model" 2)
        local family=$(get_field "$model" 4)
        local status=$(get_field "$model" 5)
        if [[ "$status" == "working" ]]; then
            echo "| $slug | $hf_id | $family |" >> "$REPORT_FILE"
        fi
    done

    {
        echo ""
        echo "## Untested Models"
        echo ""
        echo "| Model | HuggingFace ID | Family | Notes |"
        echo "|-------|----------------|--------|-------|"
    } >> "$REPORT_FILE"

    for model in "${MODELS[@]}"; do
        local slug=$(get_field "$model" 1)
        local hf_id=$(get_field "$model" 2)
        local family=$(get_field "$model" 4)
        local status=$(get_field "$model" 5)
        local notes=$(get_field "$model" 6)
        if [[ "$status" == "untested" ]]; then
            echo "| $slug | $hf_id | $family | $notes |" >> "$REPORT_FILE"
        fi
    done

    {
        echo ""
        echo "## Not Implemented"
        echo ""
        echo "These models have AleutianFOSS routing but no Sapheneia container/implementation."
        echo ""
        echo "| Model | HuggingFace ID | Family |"
        echo "|-------|----------------|--------|"
    } >> "$REPORT_FILE"

    for model in "${MODELS[@]}"; do
        local slug=$(get_field "$model" 1)
        local hf_id=$(get_field "$model" 2)
        local family=$(get_field "$model" 4)
        local status=$(get_field "$model" 5)
        if [[ "$status" == "not_implemented" ]]; then
            echo "| $slug | $hf_id | $family |" >> "$REPORT_FILE"
        fi
    done

    # Also create/update summary file
    cp "$REPORT_FILE" "$SUMMARY_FILE"

    log ""
    log "${GREEN}Report saved to: $REPORT_FILE${NC}"
    log "${GREEN}Summary saved to: $SUMMARY_FILE${NC}"
}

# =============================================================================
# Main Commands
# =============================================================================

cmd_test_all() {
    local include_backtest="${1:-false}"
    local ticker="${2:-SPY}"

    log "${CYAN}"
    cat << 'EOF'
  __  __           _      _   _____         _
 |  \/  | ___   __| | ___| | |_   _|__  ___| |_
 | |\/| |/ _ \ / _` |/ _ \ |   | |/ _ \/ __| __|
 | |  | | (_) | (_| |  __/ |   | |  __/\__ \ |_
 |_|  |_|\___/ \__,_|\___|_|   |_|\___||___/\__|
  Sapheneia Model Test Suite
EOF
    log "${NC}"

    if [[ "$include_backtest" == "true" ]]; then
        log "${CYAN}Running full tests with backtest (${ticker})...${NC}"
    fi
    log ""

    local tested=0
    local passed=0
    local failed=0
    local skipped=0

    for model in "${MODELS[@]}"; do
        local slug=$(get_field "$model" 1)
        local status=$(get_field "$model" 5)

        # Skip not_implemented models
        if [[ "$status" == "not_implemented" ]]; then
            ((skipped++))
            continue
        fi

        ((tested++))
        if run_model_test "$slug" "$include_backtest" "$ticker"; then
            ((passed++))
        else
            ((failed++))
        fi
    done

    log ""
    log "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    log "${CYAN}                    TEST SUMMARY                           ${NC}"
    log "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    log ""
    log "  Tested:  $tested"
    log "  Passed:  ${GREEN}$passed${NC}"
    log "  Failed:  ${RED}$failed${NC}"
    log "  Skipped: ${YELLOW}$skipped${NC} (not implemented)"
    if [[ "$include_backtest" == "true" ]]; then
        log ""
        log "  CSV files saved to: ${SAPHENEIA_DIR}/test_results/"
    fi
    log ""

    generate_report
}

cmd_test_quick() {
    local include_backtest="${1:-false}"
    local ticker="${2:-SPY}"

    if [[ "$include_backtest" == "true" ]]; then
        log "${CYAN}Testing known-working models with full backtest (${ticker})...${NC}"
    else
        log "${CYAN}Testing only known-working models...${NC}"
    fi
    log ""

    local tested=0
    local passed=0
    local failed=0

    for model in "${MODELS[@]}"; do
        local slug=$(get_field "$model" 1)
        local status=$(get_field "$model" 5)

        if [[ "$status" == "working" ]]; then
            ((tested++))
            if run_model_test "$slug" "$include_backtest" "$ticker"; then
                ((passed++))
            else
                ((failed++))
            fi
        fi
    done

    log ""
    log "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    log "${CYAN}                 QUICK TEST SUMMARY                        ${NC}"
    log "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    log ""
    log "  Tested:  $tested"
    log "  Passed:  ${GREEN}$passed${NC}"
    log "  Failed:  ${RED}$failed${NC}"
    if [[ "$include_backtest" == "true" ]]; then
        log ""
        log "  CSV files saved to: ${SAPHENEIA_DIR}/test_results/"
    fi
    log ""

    generate_report
}

cmd_test_model() {
    local slug="$1"
    local include_backtest="${2:-false}"
    local ticker="${3:-SPY}"

    if [[ -z "$slug" ]]; then
        log "${RED}Error: Please specify a model slug${NC}"
        exit 1
    fi
    run_model_test "$slug" "$include_backtest" "$ticker"

    log ""
    log "Results saved to: ${SAPHENEIA_DIR}/test_results/"
}

cmd_test_family() {
    local family="$1"
    local include_backtest="${2:-false}"
    local ticker="${3:-SPY}"

    if [[ -z "$family" ]]; then
        log "${RED}Error: Please specify a model family${NC}"
        exit 1
    fi

    if [[ "$include_backtest" == "true" ]]; then
        log "${CYAN}Testing all $family models with full backtest (${ticker})...${NC}"
    else
        log "${CYAN}Testing all $family models...${NC}"
    fi

    local tested=0
    local passed=0
    local failed=0

    for model in "${MODELS[@]}"; do
        local slug=$(get_field "$model" 1)
        local model_family=$(get_field "$model" 4)
        local status=$(get_field "$model" 5)

        if [[ "$model_family" == "$family" && "$status" != "not_implemented" ]]; then
            ((tested++))
            if run_model_test "$slug" "$include_backtest" "$ticker"; then
                ((passed++))
            else
                ((failed++))
            fi
        fi
    done

    log ""
    log "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    log "${CYAN}              ${family^^} FAMILY TEST SUMMARY                 ${NC}"
    log "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    log ""
    log "  Tested:  $tested"
    log "  Passed:  ${GREEN}$passed${NC}"
    log "  Failed:  ${RED}$failed${NC}"
    if [[ "$include_backtest" == "true" ]]; then
        log ""
        log "  CSV files saved to: ${SAPHENEIA_DIR}/test_results/"
    fi
    log ""

    generate_report
}

cmd_list() {
    log "${BOLD}All Models (${#MODELS[@]} total):${NC}"
    log ""
    printf "  ${BOLD}%-20s %-12s %-10s %s${NC}\n" "SLUG" "FAMILY" "STATUS" "NOTES"
    log "  ─────────────────────────────────────────────────────────────────"

    for model in "${MODELS[@]}"; do
        local slug=$(get_field "$model" 1)
        local family=$(get_field "$model" 4)
        local status=$(get_field "$model" 5)
        local notes=$(get_field "$model" 6)

        local color="$NC"
        case "$status" in
            working) color="$GREEN" ;;
            untested) color="$YELLOW" ;;
            broken) color="$RED" ;;
            not_implemented) color="$BLUE" ;;
        esac

        printf "  %-20s %-12s ${color}%-10s${NC} %s\n" "$slug" "$family" "$status" "$notes"
    done
}

cmd_help() {
    cat << EOF
${BOLD}Sapheneia Model Test Suite${NC}

Systematically test forecast models to determine working status.

${BOLD}USAGE:${NC}
    ./test-models.sh <command> [options]

${BOLD}COMMANDS:${NC}
    test              Test all testable models (skips not_implemented)
    quick             Test only known-working models (inference only)
    full              Test known-working models with full backtest + CSV export
    model <slug>      Test a specific model
    family <name>     Test all models in a family (chronos, timesfm, etc.)
    list              List all models with their status
    report            Generate status report

${BOLD}OPTIONS:${NC}
    --full            Include full backtest test (runs aleutian evaluate + export)
    --ticker <SYM>    Ticker to use for backtest (default: SPY)

${BOLD}EXAMPLES:${NC}
    ./test-models.sh quick                   # Quick test (inference only)
    ./test-models.sh full                    # Full test with backtest + CSV
    ./test-models.sh quick --full            # Same as 'full'
    ./test-models.sh quick --full --ticker QQQ  # Full test using QQQ
    ./test-models.sh model chronos-t5-tiny --full  # Full test single model
    ./test-models.sh family chronos --full   # Full test all Chronos models

${BOLD}TEST LEVELS:${NC}
    1. Container health check (is service running?)
    2. Model initialization (can load weights?)
    3. Status ready (is model ready for inference?)
    4. Inference test (can generate forecasts?)
    5. Backtest test (--full only: run backtest + export CSV)

${BOLD}OUTPUT:${NC}
    test_results/MODEL_STATUS.md             # Latest summary
    test_results/model_test_report_*.md      # Timestamped reports
    test_results/backtest_*.csv              # CSV exports (--full only)

EOF
}

# =============================================================================
# Main
# =============================================================================

main() {
    local cmd="${1:-help}"
    shift || true

    # Ensure test results directory exists
    mkdir -p "${SAPHENEIA_DIR}/test_results"

    # Parse global options
    local include_backtest="false"
    local ticker="SPY"

    while [[ "$1" == --* ]]; do
        case "$1" in
            --full)
                include_backtest="true"
                shift
                ;;
            --ticker)
                ticker="$2"
                shift 2
                ;;
            *)
                break
                ;;
        esac
    done

    case "$cmd" in
        test|all)      cmd_test_all "$include_backtest" "$ticker" ;;
        quick)         cmd_test_quick "$include_backtest" "$ticker" ;;
        full)          cmd_test_quick "true" "$ticker" ;;  # Alias for quick --full
        model)         cmd_test_model "$1" "$include_backtest" "$ticker" ;;
        family)        cmd_test_family "$1" "$include_backtest" "$ticker" ;;
        list|ls)       cmd_list ;;
        report)        generate_report ;;
        help|--help|-h) cmd_help ;;
        *)
            log "${RED}Unknown command: $cmd${NC}"
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
