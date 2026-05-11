#!/bin/bash
# =============================================================================
# Sapheneia + Aleutian Setup Script for NVIDIA Project DIGITS / DGX Spark
# =============================================================================
# This script sets up Sapheneia with AleutianFOSS-TimeSeries integration on NVIDIA DIGITS
# (Grace Blackwell) or DGX Spark systems.
#
# Hardware assumptions:
#   - NVIDIA Grace Blackwell GPU with 128GB unified memory
#   - Ubuntu 24.04 (or compatible)
#   - CUDA drivers pre-installed
#
# Usage:
#   ./scripts/setup-digits.sh
#
# What this script does:
#   1. Checks prerequisites (podman, go, gh, nvidia-smi)
#   2. Guides through GitHub authentication
#   3. Clones Sapheneia and AleutianFOSS-TimeSeries repos
#   4. Configures environment for DIGITS hardware
#   5. Starts all services with GPU acceleration
#   6. Verifies the full stack is working
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

# Configuration - DIGITS Optimized
PROJECTS_DIR="${PROJECTS_DIR:-$HOME/projects}"
SAPHENEIA_BRANCH="${SAPHENEIA_BRANCH:-aleutian_merge}"
ALEUTIAN_BRANCH="${ALEUTIAN_BRANCH:-main}"

# DIGITS/DGX Spark specific settings
DEVICE="cuda:0"  # Grace Blackwell GPU
MODELS_CACHE="$HOME/models_cache"
SIMULATIONS_ROOT="$HOME/simulations"

# =============================================================================
# Helper Functions
# =============================================================================

print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
   _____             __                   _
  / ___/____ _____  / /_  ___  ____  ____(_)___ _
  \__ \/ __ `/ __ \/ __ \/ _ \/ __ \/ __ `/ __ `/
 ___/ / /_/ / /_/ / / / /  __/ / / / /_/ / /_/ /
/____/\__,_/ .___/_/ /_/\___/_/ /_/\__,_/\__,_/
          /_/
    + AleutianFOSS-TimeSeries Integration
    for NVIDIA DIGITS / DGX Spark
EOF
    echo -e "${NC}"
}

print_header() {
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}➤ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_command() {
    command -v "$1" &> /dev/null
}

wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=${3:-60}
    local attempt=1

    echo -n "  Waiting for $name"
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo ""
            print_success "$name is ready"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    echo ""
    print_error "$name failed to start"
    return 1
}

# =============================================================================
# DIGITS Hardware Verification
# =============================================================================

verify_digits_hardware() {
    print_header "Verifying DIGITS Hardware"

    # Check NVIDIA driver
    if ! check_command nvidia-smi; then
        print_error "nvidia-smi not found. NVIDIA drivers may not be installed."
        print_error "On DIGITS, drivers should be pre-installed. Check with support."
        exit 1
    fi

    print_step "Detecting GPU hardware..."
    echo ""
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    echo ""

    # Get GPU memory
    local gpu_mem
    gpu_mem=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)

    if [ "$gpu_mem" -ge 100000 ]; then
        print_success "DIGITS/DGX Spark detected: ${gpu_mem}MB unified memory"
    elif [ "$gpu_mem" -ge 20000 ]; then
        print_success "High-end GPU detected: ${gpu_mem}MB VRAM"
    else
        print_warning "GPU memory: ${gpu_mem}MB (smaller models recommended)"
    fi

    # Check CUDA
    if check_command nvcc; then
        print_success "CUDA toolkit: $(nvcc --version | grep release | awk '{print $6}')"
    else
        print_warning "nvcc not found (CUDA toolkit may not be in PATH)"
    fi

    # Check container GPU support
    print_step "Checking container GPU support..."
    if podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.0-base nvidia-smi > /dev/null 2>&1; then
        print_success "Podman GPU passthrough working"
    else
        print_warning "GPU passthrough test failed - may need CDI configuration"
        echo "  See: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html"
    fi
}

# =============================================================================
# Prerequisites
# =============================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"

    local missing=()

    # Core tools
    check_command git && print_success "Git installed" || missing+=("git")
    check_command podman && print_success "Podman installed" || missing+=("podman")
    check_command podman-compose && print_success "podman-compose installed" || missing+=("podman-compose")
    check_command go && print_success "Go installed: $(go version | awk '{print $3}')" || missing+=("golang")
    check_command gh && print_success "GitHub CLI installed" || missing+=("gh")
    check_command curl && print_success "curl installed" || missing+=("curl")

    if [ ${#missing[@]} -gt 0 ]; then
        print_header "Installing Missing Dependencies"

        sudo apt update
        for dep in "${missing[@]}"; do
            case $dep in
                podman)
                    print_step "Installing Podman..."
                    sudo apt install -y podman
                    ;;
                podman-compose)
                    print_step "Installing podman-compose..."
                    sudo apt install -y podman-compose 2>/dev/null || pip3 install podman-compose
                    ;;
                golang)
                    print_step "Installing Go..."
                    sudo apt install -y golang-go
                    ;;
                gh)
                    print_step "Installing GitHub CLI..."
                    (type -p wget >/dev/null || sudo apt install wget -y) \
                    && sudo mkdir -p -m 755 /etc/apt/keyrings \
                    && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
                    && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
                    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
                    && sudo apt update \
                    && sudo apt install gh -y
                    ;;
                *)
                    sudo apt install -y "$dep"
                    ;;
            esac
        done
        print_success "Dependencies installed"
    fi
}

# =============================================================================
# GitHub Authentication
# =============================================================================

setup_github() {
    print_header "GitHub Authentication"

    if gh auth status &> /dev/null; then
        print_success "Already authenticated with GitHub"
        gh auth status 2>&1 | head -3
        return 0
    fi

    print_warning "GitHub authentication required for private repos"
    echo ""
    echo "Run: ${BOLD}gh auth login${NC}"
    echo ""
    echo "Select:"
    echo "  → GitHub.com"
    echo "  → HTTPS"
    echo "  → Yes (authenticate Git)"
    echo "  → Login with a web browser"
    echo ""

    read -p "Press Enter after completing GitHub authentication..."

    if gh auth status &> /dev/null; then
        print_success "GitHub authentication verified"
    else
        print_error "Authentication failed. Run 'gh auth login' and try again."
        exit 1
    fi
}

# =============================================================================
# Clone Repositories
# =============================================================================

clone_repos() {
    print_header "Cloning Repositories"

    mkdir -p "$PROJECTS_DIR"
    cd "$PROJECTS_DIR"

    # Sapheneia
    if [ -d "sapheneia" ]; then
        print_success "Sapheneia already cloned"
        cd sapheneia && git fetch origin && git checkout "$SAPHENEIA_BRANCH" && git pull || true
        cd ..
    else
        print_step "Cloning Sapheneia..."
        gh repo clone Sapheneia/sapheneia
        cd sapheneia && git checkout "$SAPHENEIA_BRANCH" && cd ..
    fi

    # AleutianFOSS-TimeSeries
    if [ -d "AleutianFOSS-TimeSeries" ]; then
        print_success "AleutianFOSS-TimeSeries already cloned"
        cd AleutianFOSS-TimeSeries && git fetch origin && git checkout "$ALEUTIAN_BRANCH" && git pull || true
        cd ..
    else
        print_step "Cloning AleutianFOSS-TimeSeries..."
        gh repo clone AleutianAI/AleutianFOSS-TimeSeries
        cd AleutianFOSS-TimeSeries && git checkout "$ALEUTIAN_BRANCH" && cd ..
    fi

    print_success "Repositories ready"
}

# =============================================================================
# Environment Configuration
# =============================================================================

configure_environment() {
    print_header "Configuring Environment"

    # Create directories
    print_step "Creating directories..."
    mkdir -p "$MODELS_CACHE"
    mkdir -p "$SIMULATIONS_ROOT"

    # Configure bashrc
    local BASHRC="$HOME/.bashrc"
    local MARKER="# === Sapheneia/Aleutian DIGITS Configuration ==="

    if grep -q "$MARKER" "$BASHRC" 2>/dev/null; then
        print_warning "Environment already configured in ~/.bashrc"
    else
        print_step "Adding environment variables to ~/.bashrc..."

        cat >> "$BASHRC" << EOF

$MARKER
# Added by setup-digits.sh on $(date)

# Sapheneia + Aleutian Integration
export ORCHESTRATOR_URL=http://localhost:12700
export API_SECRET_KEY=default_trading_api_key_please_change
export SAPHENEIA_ORCHESTRATION_URL=http://localhost:12700

# InfluxDB
export INFLUXDB_URL=http://localhost:12130
export INFLUXDB_TOKEN=aleutian-dev-token-2026
export INFLUXDB_ORG=aleutian-finance

# Project paths
export SAPHENEIA_HOME=$PROJECTS_DIR/sapheneia
export ALEUTIAN_HOME=$PROJECTS_DIR/AleutianFOSS-TimeSeries

# DIGITS GPU settings
export CUDA_VISIBLE_DEVICES=0

# Convenience aliases
alias sap='cd \$SAPHENEIA_HOME'
alias aleu='cd \$ALEUTIAN_HOME'
alias aleutian-eval='aleutian evaluate run --api-version unified'
alias stack-status='podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
alias stack-logs='podman logs -f'

# === End Sapheneia/Aleutian Configuration ===
EOF

        print_success "Environment configured"
    fi

    # Export for current session
    export ORCHESTRATOR_URL=http://localhost:12700
    export SAPHENEIA_API_KEY=default_trading_api_key_please_change
    export SAPHENEIA_ORCHESTRATION_URL=http://localhost:12700
    export INFLUXDB_URL=http://localhost:12130
    export INFLUXDB_TOKEN=aleutian-dev-token-2026
    export SAPHENEIA_HOME="$PROJECTS_DIR/sapheneia"
    export ALEUTIAN_HOME="$PROJECTS_DIR/AleutianFOSS-TimeSeries"
}

# =============================================================================
# Setup Sapheneia
# =============================================================================

setup_sapheneia() {
    print_header "Setting Up Sapheneia"

    cd "$PROJECTS_DIR/sapheneia"

    # Create network
    print_step "Creating shared network..."
    podman network create aleutian-shared 2>/dev/null || true

    # Configure .env for DIGITS
    print_step "Configuring for DIGITS hardware..."

    if [ -f .env.template ]; then
        cp .env.template .env
    fi

    # DIGITS-optimized settings
    cat > .env << EOF
# Sapheneia Environment - DIGITS Optimized
# Generated by setup-digits.sh

# Paths
MODELS_CACHE_PATH=$MODELS_CACHE
SIMULATIONS_ROOT=$SIMULATIONS_ROOT

# GPU Configuration (DIGITS Grace Blackwell)
DEVICE=cuda:0
CUDA_VISIBLE_DEVICES=0

# InfluxDB
INFLUXDB_TOKEN=aleutian-dev-token-2026
INFLUXDB_ORG=aleutian-finance
INFLUXDB_BUCKET=financial-data

# API Keys
TRADING_API_KEY=default_trading_api_key_please_change

# Model Settings (optimized for 128GB unified memory)
MAX_BATCH_SIZE=64
TORCH_DTYPE=float16
EOF

    print_success "Sapheneia configured for DIGITS"

    # Start services
    print_step "Starting Sapheneia services..."
    podman-compose up -d forecast forecast-chronos-t5-tiny trading data

    wait_for_service "http://localhost:12700/health" "Sapheneia Forecast" 90
    wait_for_service "http://localhost:12710/health" "Chronos Service" 90
}

# =============================================================================
# Setup AleutianFOSS-TimeSeries
# =============================================================================

setup_aleutian() {
    print_header "Setting Up AleutianFOSS-TimeSeries"

    cd "$PROJECTS_DIR/AleutianFOSS-TimeSeries"

    # Build CLI
    print_step "Building Aleutian CLI..."
    go build -o aleutian ./cmd/aleutian

    print_step "Installing to /usr/local/bin..."
    sudo cp aleutian /usr/local/bin/
    print_success "Aleutian CLI installed"

    # Build and start
    print_step "Building orchestrator container..."
    podman-compose build orchestrator

    print_step "Starting Aleutian stack..."
    aleutian stack start --forecast-mode sapheneia --skip-model-check

    sleep 10

    # Reconnect data service
    print_step "Reconnecting services..."
    cd "$PROJECTS_DIR/sapheneia"
    podman restart sapheneia-data 2>/dev/null || true
}

# =============================================================================
# Initialize and Verify
# =============================================================================

initialize_models() {
    print_header "Initializing Forecast Models"

    print_step "Warming up Chronos model on GPU..."

    curl -s -X POST http://localhost:12710/forecast/v1/chronos/initialization \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer default_trading_api_key_please_change" \
        -d '{}' > /dev/null

    print_step "Testing forecast endpoint..."

    local response
    response=$(curl -s -X POST http://localhost:12700/orchestration/v1/predict \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer default_trading_api_key_please_change" \
        -d '{"ticker":"SPY","model":"amazon/chronos-t5-tiny","context":[100,101,102,103,104],"prediction_length":5}')

    if echo "$response" | grep -q "predictions"; then
        print_success "Forecast endpoint working"
    else
        print_warning "Forecast response: $response"
    fi
}

verify_setup() {
    print_header "Verification"

    echo ""
    print_step "Running containers:"
    podman ps --format "table {{.Names}}\t{{.Status}}" | grep -E "sapheneia|aleutian|orchestrator|influx"

    echo ""
    print_step "Service health:"

    local all_ok=true
    for endpoint in \
        "http://localhost:12700/health|Sapheneia Orchestration" \
        "http://localhost:12710/health|Chronos Forecast" \
        "http://localhost:12130/health|InfluxDB"
    do
        IFS='|' read -r url name <<< "$endpoint"
        if curl -s "$url" > /dev/null 2>&1; then
            print_success "$name"
        else
            print_error "$name"
            all_ok=false
        fi
    done

    echo ""
    if [ "$all_ok" = true ]; then
        print_success "All services healthy!"
    else
        print_warning "Some services need attention"
    fi
}

print_summary() {
    print_header "Setup Complete!"

    echo -e "${GREEN}${BOLD}"
    cat << 'EOF'
  ____  ___ ____ ___ _____ ____    ____  _____    _    ______   __
 |  _ \|_ _/ ___|_ _|_   _/ ___|  |  _ \| ____|  / \  |  _ \ \ / /
 | | | || | |  _ | |  | | \___ \  | |_) |  _|   / _ \ | | | \ V /
 | |_| || | |_| || |  | |  ___) | |  _ <| |___ / ___ \| |_| || |
 |____/|___\____|___| |_| |____/  |_| \_\_____/_/   \_\____/ |_|

EOF
    echo -e "${NC}"

    echo "Your DIGITS system is configured for Sapheneia + AleutianFOSS-TimeSeries!"
    echo ""
    echo -e "${CYAN}Quick Commands:${NC}"
    echo ""
    echo "  # Run a backtest evaluation"
    echo "  aleutian evaluate run --config strategies/spy_threshold_v1.yaml --api-version unified"
    echo ""
    echo "  # Or use the alias (after sourcing ~/.bashrc)"
    echo "  aleutian-eval --config strategies/spy_threshold_v1.yaml"
    echo ""
    echo "  # Check stack status"
    echo "  stack-status"
    echo ""
    echo -e "${CYAN}Service Endpoints:${NC}"
    echo ""
    echo "  Sapheneia Orchestration:  http://localhost:12700"
    echo "  Chronos Forecast:         http://localhost:12710"
    echo "  InfluxDB:                 http://localhost:12130"
    echo ""
    echo -e "${YELLOW}Run 'source ~/.bashrc' to activate aliases in this terminal.${NC}"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    print_banner

    echo "This script configures Sapheneia + AleutianFOSS-TimeSeries on NVIDIA DIGITS."
    echo ""
    read -p "Continue? [Y/n] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Nn]$ ]] && exit 0

    verify_digits_hardware
    check_prerequisites
    setup_github
    clone_repos
    configure_environment
    setup_sapheneia
    setup_aleutian
    initialize_models
    verify_setup
    print_summary
}

main "$@"
