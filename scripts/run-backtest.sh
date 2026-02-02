#!/bin/bash
# =============================================================================
# Interactive Backtest Runner
# =============================================================================
# Pick a model, pick a ticker, confirm, and run.
#
# Usage:
#   ./run-backtest.sh                     # Interactive mode
#   ./run-backtest.sh --list              # List available models and tickers
#   ./run-backtest.sh --model chronos-t5-tiny --ticker SPY  # Direct run
#   ./run-backtest.sh --model chronos-t5-tiny --ticker SPY --yes  # Skip confirmation
# =============================================================================

set -o pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAPHENEIA_DIR="$(dirname "$SCRIPT_DIR")"
STRATEGIES_DIR="${SAPHENEIA_DIR}/simulations/strategies"
RESULTS_DIR="${SAPHENEIA_DIR}/test_results"

# Available models (working ones)
declare -a MODELS=(
    "chronos-t5-tiny|amazon/chronos-t5-tiny|12710|Fastest, good for testing"
    "chronos-t5-mini|amazon/chronos-t5-mini|12711|Fast, slightly better accuracy"
    "chronos-t5-small|amazon/chronos-t5-small|12712|Balanced speed/accuracy"
    "chronos-t5-base|amazon/chronos-t5-base|12713|Good accuracy, slower"
    "chronos-t5-large|amazon/chronos-t5-large|12714|Best accuracy, slowest"
    "timesfm-2-0|google/timesfm-2.0-500m-pytorch|12721|Google TimesFM 2.0"
)

# Get tickers from strategy directories
get_tickers() {
    find "$STRATEGIES_DIR" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | grep -v results | sort
}

# =============================================================================
# Display Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}            ${BOLD}Sapheneia Interactive Backtest Runner${NC}            ${CYAN}║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

list_models() {
    echo -e "${BOLD}Available Models:${NC}"
    echo ""
    local i=1
    for model in "${MODELS[@]}"; do
        local slug=$(echo "$model" | cut -d'|' -f1)
        local hf_id=$(echo "$model" | cut -d'|' -f2)
        local port=$(echo "$model" | cut -d'|' -f3)
        local desc=$(echo "$model" | cut -d'|' -f4)

        # Check if running
        local status="${RED}●${NC}"
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/health" 2>/dev/null | grep -q "200"; then
            status="${GREEN}●${NC}"
        fi

        printf "  ${BOLD}%2d)${NC} ${status} %-20s ${DIM}%s${NC}\n" "$i" "$slug" "$desc"
        ((i++))
    done
    echo ""
    echo -e "  ${GREEN}●${NC} = running    ${RED}●${NC} = not running"
    echo ""
}

list_tickers() {
    echo -e "${BOLD}Available Tickers:${NC}"
    echo ""
    local tickers=($(get_tickers))
    local cols=6
    local i=0

    for ticker in "${tickers[@]}"; do
        printf "  %-8s" "$ticker"
        ((i++))
        if (( i % cols == 0 )); then
            echo ""
        fi
    done
    if (( i % cols != 0 )); then
        echo ""
    fi
    echo ""
    echo -e "  ${DIM}(${#tickers[@]} tickers available)${NC}"
    echo ""
}

list_all() {
    print_header
    list_models
    list_tickers
}

# =============================================================================
# Interactive Selection
# =============================================================================

select_model() {
    list_models

    while true; do
        echo -ne "${BOLD}Select model [1-${#MODELS[@]}]:${NC} "
        read -r choice

        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#MODELS[@]} )); then
            SELECTED_MODEL=$(echo "${MODELS[$((choice-1))]}" | cut -d'|' -f1)
            SELECTED_HF_ID=$(echo "${MODELS[$((choice-1))]}" | cut -d'|' -f2)
            SELECTED_PORT=$(echo "${MODELS[$((choice-1))]}" | cut -d'|' -f3)
            echo -e "  ${GREEN}✓${NC} Selected: ${BOLD}$SELECTED_MODEL${NC}"
            echo ""
            return 0
        else
            echo -e "  ${RED}Invalid choice. Enter 1-${#MODELS[@]}${NC}"
        fi
    done
}

select_ticker() {
    list_tickers

    local tickers=($(get_tickers))

    while true; do
        echo -ne "${BOLD}Enter ticker symbol:${NC} "
        read -r choice
        choice=$(echo "$choice" | tr '[:lower:]' '[:upper:]')

        if [[ " ${tickers[*]} " =~ " ${choice} " ]]; then
            SELECTED_TICKER="$choice"
            echo -e "  ${GREEN}✓${NC} Selected: ${BOLD}$SELECTED_TICKER${NC}"
            echo ""
            return 0
        else
            echo -e "  ${RED}Ticker '$choice' not found. Available: ${tickers[*]:0:5}...${NC}"
        fi
    done
}

# =============================================================================
# Strategy Detection
# =============================================================================

find_strategy_file() {
    local ticker="$1"
    local model="$2"

    # Convert model slug to filename pattern (chronos-t5-tiny -> chronos_t5_tiny)
    local pattern="${model//-/_}"
    local ticker_lower=$(echo "$ticker" | tr '[:upper:]' '[:lower:]')

    # Try exact match first
    local strategy_file="${STRATEGIES_DIR}/${ticker}/${ticker_lower}_${pattern}.yaml"

    if [[ -f "$strategy_file" ]]; then
        echo "$strategy_file"
        return 0
    fi

    # Try finding with glob
    local found=$(find "${STRATEGIES_DIR}/${ticker}" -name "*${pattern}*.yaml" 2>/dev/null | head -1)
    if [[ -n "$found" ]]; then
        echo "$found"
        return 0
    fi

    return 1
}

# =============================================================================
# Confirmation and Execution
# =============================================================================

show_confirmation() {
    local strategy_file="$1"

    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}                    BACKTEST CONFIGURATION                     ${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}Model:${NC}     $SELECTED_MODEL"
    echo -e "  ${BOLD}HF ID:${NC}     $SELECTED_HF_ID"
    echo -e "  ${BOLD}Port:${NC}      $SELECTED_PORT"
    echo -e "  ${BOLD}Ticker:${NC}    $SELECTED_TICKER"
    echo -e "  ${BOLD}Strategy:${NC}  $(basename "$strategy_file")"
    echo ""

    # Show strategy details
    if [[ -f "$strategy_file" ]]; then
        echo -e "${DIM}Strategy details:${NC}"
        grep -E "^  (start_date|end_date|context_size|horizon_size|initial_capital):" "$strategy_file" | sed 's/^/    /'
        echo ""
    fi

    # Check if model is running
    echo -ne "  Model status: "
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${SELECTED_PORT}/health" 2>/dev/null | grep -q "200"; then
        echo -e "${GREEN}RUNNING${NC}"
    else
        echo -e "${RED}NOT RUNNING${NC}"
        echo ""
        echo -e "  ${YELLOW}⚠ Model container is not running!${NC}"
        echo -e "  ${DIM}Start it with: ./scripts/model-manager.sh start $SELECTED_MODEL${NC}"
    fi
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
}

confirm_and_run() {
    local strategy_file="$1"
    local auto_yes="$2"

    show_confirmation "$strategy_file"

    if [[ "$auto_yes" != "true" ]]; then
        echo ""
        echo -ne "${BOLD}Proceed with backtest? [Y/n]:${NC} "
        read -r confirm

        if [[ "$confirm" =~ ^[Nn] ]]; then
            echo -e "${YELLOW}Aborted.${NC}"
            exit 0
        fi
    fi

    echo ""
    echo -e "${CYAN}Starting backtest...${NC}"
    echo ""

    run_backtest "$strategy_file"
}

run_backtest() {
    local strategy_file="$1"
    local start_time=$(date +%s)

    # Create results directory
    mkdir -p "$RESULTS_DIR"

    # Run the backtest
    echo -e "${DIM}$ aleutian evaluate run --config $strategy_file --api-version legacy${NC}"
    echo ""

    local output
    output=$(aleutian evaluate run --config "$strategy_file" --api-version legacy 2>&1)
    local exit_code=$?

    echo "$output"
    echo ""

    # Extract Run ID
    local run_id
    run_id=$(echo "$output" | grep "Run ID:" | awk '{print $NF}' | tail -1)

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

    if [[ -n "$run_id" ]]; then
        echo -e "${GREEN}✓ Backtest completed in ${duration}s${NC}"
        echo -e "  Run ID: ${BOLD}$run_id${NC}"
        echo ""

        # Export to CSV
        echo -e "Exporting to CSV..."
        local export_output
        export_output=$(aleutian evaluate export "$run_id" 2>&1)

        if echo "$export_output" | grep -q "Export complete"; then
            local csv_file="backtest_${run_id}.csv"
            if [[ -f "$csv_file" ]]; then
                mv "$csv_file" "${RESULTS_DIR}/"
                echo -e "${GREEN}✓ CSV saved: ${RESULTS_DIR}/${csv_file}${NC}"
            fi
        else
            echo -e "${YELLOW}⚠ CSV export issue: $(echo "$export_output" | tail -1)${NC}"
        fi
    else
        echo -e "${RED}✗ Backtest failed${NC}"
        echo -e "  Exit code: $exit_code"
        echo -e "  Check output above for errors"
    fi

    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    local mode="interactive"
    local auto_yes="false"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --list|-l)
                mode="list"
                shift
                ;;
            --model|-m)
                SELECTED_MODEL="$2"
                mode="direct"
                shift 2
                ;;
            --ticker|-t)
                SELECTED_TICKER=$(echo "$2" | tr '[:lower:]' '[:upper:]')
                shift 2
                ;;
            --yes|-y)
                auto_yes="true"
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --list, -l              List available models and tickers"
                echo "  --model, -m MODEL       Specify model (e.g., chronos-t5-tiny)"
                echo "  --ticker, -t TICKER     Specify ticker (e.g., SPY)"
                echo "  --yes, -y               Skip confirmation prompt"
                echo "  --help, -h              Show this help"
                echo ""
                echo "Examples:"
                echo "  $0                      # Interactive mode"
                echo "  $0 --list               # List models and tickers"
                echo "  $0 -m chronos-t5-tiny -t SPY        # Direct run with confirmation"
                echo "  $0 -m chronos-t5-tiny -t SPY --yes  # Direct run, skip confirmation"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # List mode
    if [[ "$mode" == "list" ]]; then
        list_all
        exit 0
    fi

    print_header

    # Interactive mode - select model
    if [[ -z "$SELECTED_MODEL" ]]; then
        select_model
    else
        # Validate provided model
        local found=false
        for model in "${MODELS[@]}"; do
            local slug=$(echo "$model" | cut -d'|' -f1)
            if [[ "$slug" == "$SELECTED_MODEL" ]]; then
                SELECTED_HF_ID=$(echo "$model" | cut -d'|' -f2)
                SELECTED_PORT=$(echo "$model" | cut -d'|' -f3)
                found=true
                break
            fi
        done
        if [[ "$found" != "true" ]]; then
            echo -e "${RED}Error: Unknown model '$SELECTED_MODEL'${NC}"
            echo "Available: ${MODELS[*]%%|*}"
            exit 1
        fi
    fi

    # Interactive mode - select ticker
    if [[ -z "$SELECTED_TICKER" ]]; then
        select_ticker
    else
        # Validate provided ticker
        local tickers=($(get_tickers))
        if [[ ! " ${tickers[*]} " =~ " ${SELECTED_TICKER} " ]]; then
            echo -e "${RED}Error: Unknown ticker '$SELECTED_TICKER'${NC}"
            echo "Available: ${tickers[*]}"
            exit 1
        fi
    fi

    # Find strategy file
    local strategy_file
    strategy_file=$(find_strategy_file "$SELECTED_TICKER" "$SELECTED_MODEL")

    if [[ -z "$strategy_file" || ! -f "$strategy_file" ]]; then
        echo -e "${RED}Error: No strategy file found for $SELECTED_TICKER + $SELECTED_MODEL${NC}"
        echo "Expected: ${STRATEGIES_DIR}/${SELECTED_TICKER}/${SELECTED_TICKER,,}_${SELECTED_MODEL//-/_}.yaml"
        exit 1
    fi

    # Confirm and run
    confirm_and_run "$strategy_file" "$auto_yes"
}

main "$@"
