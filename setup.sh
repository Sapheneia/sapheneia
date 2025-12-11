#!/bin/bash

# =============================================================================
# Sapheneia Setup Script
#
# This script manages three Sapheneia applications:
# - forecast: API (forecasting models) and UI application
# - trading: Trading strategies API application
# - metrics: Evaluation metrics API application
#
# Usage:
#   # Forecast Application
#   ./setup.sh init forecast                    # Initialize forecast application
#   ./setup.sh run-venv forecast api           # Run API only
#   ./setup.sh run-venv forecast ui            # Run UI only
#   ./setup.sh run-venv forecast all           # Run both API and UI
#   ./setup.sh run-docker forecast api          # Run API container
#   ./setup.sh run-docker forecast ui           # Run UI container
#   ./setup.sh run-docker forecast all          # Run both API and UI containers
#   ./setup.sh stop forecast                    # Stop forecast services
#
#   # Trading Application
#   ./setup.sh init trading                     # Initialize trading application
#   ./setup.sh run-venv trading                # Run trading service
#   ./setup.sh run-docker trading              # Run trading container
#   ./setup.sh stop trading                     # Stop trading service
#
#   # Metrics Application
#   ./setup.sh init metrics                     # Initialize metrics application
#   ./setup.sh run-venv metrics                # Run metrics API service
#   ./setup.sh stop metrics                     # Stop metrics service
#
#   # Help
#   ./setup.sh --help forecast                  # Help for forecast application
#   ./setup.sh --help trading                   # Help for trading application
#   ./setup.sh --help metrics                   # Help for metrics application
#   ./setup.sh --help                           # General help
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="sapheneia"
PYTHON_VERSION="3.11"
VENV_NAME=".venv"
API_PORT=8000
UI_PORT=8080
TRADING_PORT=9000
METRICS_PORT=8001

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is in use
port_in_use() {
    lsof -ti :$1 >/dev/null 2>&1
}

# Function to kill process on port
kill_port() {
    local port=$1
    if port_in_use $port; then
        print_status "Killing process on port $port..."
        lsof -ti :$port | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

# Function to detect system architecture
detect_system() {
    ARCH=$(uname -m)
    OS=$(uname -s)

    print_status "Detected system: $OS ($ARCH)"

    # Determine if we're on Apple Silicon
    if [[ "$OS" == "Darwin" && "$ARCH" == "arm64" ]]; then
        APPLE_SILICON=true
        print_status "Apple Silicon detected - will use PyTorch TimesFM backend"
    else
        APPLE_SILICON=false
        print_status "x86_64 architecture detected - will use JAX TimesFM backend"
    fi
}

# Function to install UV package manager
install_uv() {
    print_header "Installing UV Package Manager"

    if command_exists uv; then
        print_status "UV already installed: $(uv --version)"
        return
    fi

    print_status "Installing UV package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Add UV to PATH for current session
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    if command_exists uv; then
        print_status "UV installed successfully: $(uv --version)"
    else
        print_error "UV installation failed"
        exit 1
    fi
}

# Function to setup Python environment
setup_python_env() {
    print_header "Setting up Python Environment"

    if [[ -d "$VENV_NAME" ]]; then
        print_status "Virtual environment already exists: $VENV_NAME"
    else
        print_status "Creating Python $PYTHON_VERSION virtual environment..."
        uv venv $VENV_NAME --python $PYTHON_VERSION
    fi

    print_status "Virtual environment ready: $VENV_NAME"
}

# Function to install dependencies
install_dependencies() {
    print_header "Installing Dependencies"

    print_status "Installing from pyproject.toml..."
    uv pip install -e .

    print_status "Installing dev dependencies (pytest, test tools)..."
    uv pip install -e .[dev]

    print_status "Installing python-dotenv for environment management..."
    uv pip install python-dotenv

    print_status "Dependencies installed successfully"
}

# Function to setup environment file
setup_env_file() {
    print_header "Setting up Environment File"

    if [[ -f ".env" ]]; then
        print_status ".env file already exists"
    else
        if [[ -f ".env.template" ]]; then
            print_status "Copying .env.template to .env..."
            cp .env.template .env
            print_warning "Please edit .env and set your API_SECRET_KEY"
        else
            print_warning ".env.template not found, creating minimal .env..."
            cat > .env << 'EOF'
# Sapheneia API Configuration
API_SECRET_KEY="$(openssl rand -base64 32)"
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# TimesFM Model Configuration
TIMESFM_DEFAULT_CONTEXT_LEN=64
TIMESFM_DEFAULT_HORIZON_LEN=24

# MLflow Configuration (optional)
MLFLOW_TRACKING_URI=http://localhost:5000

# UI Configuration
UI_API_BASE_URL=http://localhost:8000
EOF
            print_status ".env file created with default values"
        fi
    fi
}

# Function to initialize environment
cmd_init() {
    local application="${1:-forecast}"  # Default to forecast for backward compatibility

    # Check if we're in the right directory
    if [[ ! -f "pyproject.toml" ]]; then
        print_error "Please run this script from the sapheneia project root directory"
        print_error "Expected file: pyproject.toml"
        exit 1
    fi

    case $application in
        forecast)
            print_header "Initializing Forecast Application Environment"

            # Detect system
            detect_system

            # Install UV
            install_uv

            # Setup Python environment
            setup_python_env

            # Install dependencies
            install_dependencies

            # Setup environment file
            setup_env_file

            # Create necessary directories
            mkdir -p forecast/models/timesfm20/local
            mkdir -p data/uploads
            mkdir -p data/results
            mkdir -p logs

            print_header "Initialization Complete!"
            print_status "Forecast application environment is ready!"
            echo
            print_status "Next steps:"
            echo "  1. Edit .env file and set your API_SECRET_KEY"
            echo "  2. Run API: ./setup.sh run-venv forecast api"
            echo "  3. Run UI: ./setup.sh run-venv forecast ui"
            echo "  4. Or run both: ./setup.sh run-venv forecast all"
            echo "  5. Run tests: ./setup.sh test"
            echo
            ;;
        trading)
            print_header "Initializing Trading Application Environment"

            # Detect system
            detect_system

            # Install UV
            install_uv

            # Setup Python environment
            setup_python_env

            # Install dependencies
            install_dependencies

            # Setup environment file (if not exists)
            setup_env_file

            # Create necessary directories
            mkdir -p logs

            print_header "Initialization Complete!"
            print_status "Trading application environment is ready!"
            echo
            print_status "Next steps:"
            echo "  1. Edit .env file and set your TRADING_API_KEY (min 32 chars)"
            echo "  2. Run trading: ./setup.sh run-venv trading"
            echo "  3. Run tests: ./setup.sh test"
            echo
            ;;
        metrics)
            print_header "Initializing Metrics Application Environment"

            # Detect system
            detect_system

            # Install UV
            install_uv

            # Setup Python environment
            setup_python_env

            # Install dependencies
            install_dependencies

            # Setup environment file (if not exists)
            setup_env_file

            # Create necessary directories
            mkdir -p logs

            print_header "Initialization Complete!"
            print_status "Metrics application environment is ready!"
            echo
            print_status "Next steps:"
            echo "  1. Run metrics API: ./setup.sh run-venv metrics"
            echo "  2. Run tests: ./setup.sh test"
            echo
            ;;
        *)
            print_error "Unknown application: $application"
            print_error "Usage: ./setup.sh init [forecast|trading|metrics]"
            exit 1
            ;;
    esac
}

# Function to run API with venv
run_api_venv() {
    print_header "Starting API Server (Virtual Environment)"

    kill_port $API_PORT

    print_status "Starting API on port $API_PORT..."
    uv run uvicorn forecast.main:app --host 0.0.0.0 --port $API_PORT --reload &

    sleep 3

    if port_in_use $API_PORT; then
        print_status "✅ API server running at http://localhost:$API_PORT"
        print_status "   Health: http://localhost:$API_PORT/health"
        print_status "   Docs: http://localhost:$API_PORT/docs"
    else
        print_error "Failed to start API server"
        exit 1
    fi
}

# Function to run UI with venv
run_ui_venv() {
    print_header "Starting UI Server (Virtual Environment)"

    kill_port $UI_PORT

    print_status "Starting UI on port $UI_PORT..."
    cd ui && uv run python app.py > /tmp/sapheneia_ui.log 2>&1 &
    cd ..

    sleep 3

    if port_in_use $UI_PORT; then
        print_status "✅ UI server running at http://localhost:$UI_PORT"
    else
        print_error "Failed to start UI server"
        exit 1
    fi
}

# Function to run Trading with venv
run_trading_venv() {
    print_header "Starting Trading Strategies API (Virtual Environment)"

    kill_port $TRADING_PORT

    print_status "Starting Trading API on port $TRADING_PORT..."
    uv run uvicorn trading.main:app --host 0.0.0.0 --port $TRADING_PORT --reload &

    sleep 3

    if port_in_use $TRADING_PORT; then
        print_status "✅ Trading API server running at http://localhost:$TRADING_PORT"
        print_status "   Health: http://localhost:$TRADING_PORT/health"
        print_status "   Docs: http://localhost:$TRADING_PORT/docs"
    else
        print_error "Failed to start Trading API server"
        exit 1
    fi
}

# Function to run Metrics API with venv
run_metrics_api_venv() {
    print_header "Starting Metrics API (Virtual Environment)"

    kill_port $METRICS_PORT

    print_status "Starting Metrics API on port $METRICS_PORT..."
    uv run uvicorn metrics.main:app --host 0.0.0.0 --port $METRICS_PORT --reload &

    sleep 3

    if port_in_use $METRICS_PORT; then
        print_status "✅ Metrics API server running at http://localhost:$METRICS_PORT"
        print_status "   Health: http://localhost:$METRICS_PORT/health"
        print_status "   Docs: http://localhost:$METRICS_PORT/docs"
    else
        print_error "Failed to start Metrics API server"
        exit 1
    fi
}

# Function to run with venv
cmd_run_venv() {
    local application=$1
    local service=$2

    if [[ ! -d "$VENV_NAME" ]]; then
        print_error "Virtual environment not found. Run: ./setup.sh init $application"
        exit 1
    fi

    case $application in
        forecast)
            case $service in
                api)
                    run_api_venv
                    ;;
                ui)
                    run_ui_venv
                    ;;
                all)
                    run_api_venv
                    echo
                    run_ui_venv
                    echo
                    print_header "All Forecast Services Started"
                    print_status "API: http://localhost:$API_PORT"
                    print_status "UI: http://localhost:$UI_PORT"
                    echo
                    print_status "Press Ctrl+C to stop (servers run in background)"
                    print_status "To stop: ./setup.sh stop forecast"
                    ;;
                *)
                    print_error "Unknown service: $service"
                    print_error "Usage: ./setup.sh run-venv forecast [api|ui|all]"
                    exit 1
                    ;;
            esac
            ;;
        trading)
            if [[ -z "$service" || "$service" == "trading" ]]; then
                run_trading_venv
            else
                print_error "Unknown service: $service"
                print_error "Usage: ./setup.sh run-venv trading"
                exit 1
            fi
            ;;
        metrics)
            if [[ -z "$service" || "$service" == "metrics" ]]; then
                run_metrics_api_venv
            else
                print_error "Unknown service: $service"
                print_error "Usage: ./setup.sh run-venv metrics"
                exit 1
            fi
            ;;
        *)
            if [[ "$application" == "all" ]]; then
                print_error "Invalid command. Use: ./setup.sh run-venv forecast all"
                exit 1
            fi
            print_error "Unknown application: $application"
            print_error "Usage: ./setup.sh run-venv [forecast|trading|metrics] [service]"
            exit 1
            ;;
    esac
}

# Function to run with Docker
cmd_run_docker() {
    local application=$1
    local service=$2

    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Set Docker context to desktop-linux for Docker Desktop on macOS
    export DOCKER_CONTEXT=desktop-linux

    # Check for docker compose (new) or docker-compose (legacy)
    if ! docker compose version >/dev/null 2>&1 && ! command_exists docker-compose; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    # Use docker compose (new) if available, otherwise docker-compose (legacy)
    local COMPOSE_CMD="docker compose"
    if ! docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    fi

    print_header "Starting Services with Docker"

    case $application in
        forecast)
            case $service in
                api)
                    print_status "Building and starting Forecast API container..."
                    $COMPOSE_CMD up -d forecast
                    sleep 3
                    print_status "✅ Forecast API running at http://localhost:$API_PORT"
                    ;;
                ui)
                    print_status "Building and starting UI container..."
                    $COMPOSE_CMD up -d ui
                    sleep 3
                    print_status "✅ UI running at http://localhost:$UI_PORT"
                    ;;
                all)
                    print_status "Building and starting forecast containers..."
                    $COMPOSE_CMD up -d forecast ui
                    sleep 5
                    print_status "✅ Forecast API running at http://localhost:$API_PORT"
                    print_status "✅ UI running at http://localhost:$UI_PORT"
                    echo
                    print_status "View logs: $COMPOSE_CMD logs -f"
                    print_status "To stop: ./setup.sh stop forecast"
                    ;;
                *)
                    print_error "Unknown service: $service"
                    print_error "Usage: ./setup.sh run-docker forecast [api|ui|all]"
                    exit 1
                    ;;
            esac
            ;;
        trading)
            if [[ -z "$service" || "$service" == "trading" ]]; then
                print_status "Building and starting Trading container..."
                $COMPOSE_CMD up -d trading
                sleep 3
                print_status "✅ Trading API running at http://localhost:$TRADING_PORT"
                echo
                print_status "View logs: $COMPOSE_CMD logs -f trading"
                print_status "To stop: ./setup.sh stop trading"
            else
                print_error "Unknown service: $service"
                print_error "Usage: ./setup.sh run-docker trading"
                exit 1
            fi
            ;;
        *)
            if [[ "$application" == "all" ]]; then
                print_error "Invalid command. Use: ./setup.sh run-docker forecast all"
                exit 1
            fi
            print_error "Unknown application: $application"
            print_error "Usage: ./setup.sh run-docker [forecast|trading] [service]"
            exit 1
            ;;
    esac
}

# Function to run tests
cmd_test() {
    print_header "Running Tests"

    if ! command_exists uv; then
        print_error "uv is not installed. Run: ./setup.sh init"
        exit 1
    fi

    print_status "Running test suite with pytest..."
    uv run pytest "$@"
}

# Function to stop services
cmd_stop() {
    local application=$1

    if [[ -z "$application" ]]; then
        print_error "Application name required"
        print_error "Usage: ./setup.sh stop [forecast|trading]"
        exit 1
    fi

    case $application in
        forecast)
            print_header "Stopping Forecast Services"

            # Stop Docker services
            if command_exists docker; then
                print_status "Stopping Docker containers..."
                docker stop sapheneia-forecast sapheneia-ui 2>/dev/null || true
                docker rm sapheneia-forecast sapheneia-ui 2>/dev/null || true
                print_status "Docker containers stopped and removed"
            fi

            print_status "Stopping venv ports..."
            kill_port $API_PORT
            kill_port $UI_PORT

            print_status "✅ Forecast services stopped"
            ;;
        trading)
            print_header "Stopping Trading Services"

            # Stop Docker services
            if command_exists docker; then
                print_status "Stopping Docker containers..."
                docker stop sapheneia-trading 2>/dev/null || true
                docker rm sapheneia-trading 2>/dev/null || true
                print_status "Docker containers stopped and removed"
            fi

            print_status "Stopping venv ports..."
            kill_port $TRADING_PORT

            print_status "✅ Trading services stopped"
            ;;
        metrics)
            print_header "Stopping Metrics Services"

            # Stop Docker services
            if command_exists docker; then
                print_status "Stopping Docker containers..."
                docker stop sapheneia-metrics 2>/dev/null || true
                docker rm sapheneia-metrics 2>/dev/null || true
                print_status "Docker containers stopped and removed"
            fi

            print_status "Stopping venv ports..."
            kill_port $METRICS_PORT

            print_status "✅ Metrics services stopped"
            ;;
        *)
            print_error "Unknown application: $application"
            print_error "Usage: ./setup.sh stop [forecast|trading|metrics]"
            exit 1
            ;;
    esac
}

# Function to show help for forecast application
show_help_forecast() {
    cat << EOF
${BLUE}Sapheneia Forecast Application Setup${NC}

${GREEN}USAGE:${NC}
    ./setup.sh COMMAND forecast [OPTIONS]

${GREEN}COMMANDS:${NC}
    init forecast                    Initialize forecast application environment
    run-venv forecast [api|ui|all]  Run services with virtual environment
    run-docker forecast [api|ui|all] Run services with Docker
    stop forecast                    Stop forecast services
    test                             Run test suite with pytest

${GREEN}EXAMPLES:${NC}
    ${BLUE}# Initialize environment${NC}
    ./setup.sh init forecast

    ${BLUE}# Run with virtual environment${NC}
    ./setup.sh run-venv forecast api      # Run only API server
    ./setup.sh run-venv forecast ui       # Run only UI server
    ./setup.sh run-venv forecast all      # Run both API and UI

    ${BLUE}# Run with Docker${NC}
    ./setup.sh run-docker forecast api    # Run only API container
    ./setup.sh run-docker forecast ui     # Run only UI container
    ./setup.sh run-docker forecast all    # Run both with Docker Compose

    ${BLUE}# Stop services${NC}
    ./setup.sh stop forecast

${GREEN}PORTS:${NC}
    - API Server: $API_PORT
    - UI Server: $UI_PORT

${GREEN}ENVIRONMENT:${NC}
    - Python Version: $PYTHON_VERSION
    - Virtual Environment: $VENV_NAME
    - Configuration: .env file

EOF
}

# Function to show help for trading application
show_help_trading() {
    cat << EOF
${BLUE}Sapheneia Trading Application Setup${NC}

${GREEN}USAGE:${NC}
    ./setup.sh COMMAND trading [OPTIONS]

${GREEN}COMMANDS:${NC}
    init trading                     Initialize trading application environment
    run-venv trading                Run trading service with virtual environment
    run-docker trading              Run trading service with Docker
    stop trading                     Stop trading services
    test                             Run test suite with pytest

${GREEN}EXAMPLES:${NC}
    ${BLUE}# Initialize environment${NC}
    ./setup.sh init trading

    ${BLUE}# Run with virtual environment${NC}
    ./setup.sh run-venv trading

    ${BLUE}# Run with Docker${NC}
    ./setup.sh run-docker trading

    ${BLUE}# Stop services${NC}
    ./setup.sh stop trading

${GREEN}PORTS:${NC}
    - Trading API Server: $TRADING_PORT

${GREEN}ENVIRONMENT:${NC}
    - Python Version: $PYTHON_VERSION
    - Virtual Environment: $VENV_NAME
    - Configuration: .env file (TRADING_API_KEY required, min 32 chars)

EOF
}

# Function to show help for metrics application
show_help_metrics() {
    cat << EOF
${BLUE}Sapheneia Metrics Application Setup${NC}

${GREEN}USAGE:${NC}
    ./setup.sh COMMAND metrics [OPTIONS]

${GREEN}COMMANDS:${NC}
    init metrics                     Initialize metrics application environment
    run-venv metrics                Run metrics API service with virtual environment
    stop metrics                     Stop metrics services
    test                             Run test suite with pytest

${GREEN}EXAMPLES:${NC}
    ${BLUE}# Initialize environment${NC}
    ./setup.sh init metrics

    ${BLUE}# Run with virtual environment${NC}
    ./setup.sh run-venv metrics

    ${BLUE}# Stop services${NC}
    ./setup.sh stop metrics

${GREEN}PORTS:${NC}
    - Metrics API Server: $METRICS_PORT

${GREEN}ENVIRONMENT:${NC}
    - Python Version: $PYTHON_VERSION
    - Virtual Environment: $VENV_NAME
    - Configuration: .env file

EOF
}

# Function to show general help
show_help() {
    local application="${1:-}"

    case $application in
        forecast)
            show_help_forecast
            ;;
        trading)
            show_help_trading
            ;;
        metrics)
            show_help_metrics
            ;;
        *)
            cat << EOF
${BLUE}Sapheneia Setup Script${NC}

${GREEN}OVERVIEW:${NC}
    This script manages three Sapheneia applications:
    - ${GREEN}forecast${NC}: API (forecasting models) and UI application
    - ${GREEN}trading${NC}: Trading strategies API application
    - ${GREEN}metrics${NC}: Evaluation metrics API application

${GREEN}USAGE:${NC}
    ./setup.sh COMMAND [APPLICATION] [OPTIONS]

${GREEN}COMMANDS:${NC}
    init [forecast|trading|metrics]          Initialize application environment
    run-venv [forecast|trading|metrics] [service] Run services with virtual environment
    run-docker [forecast|trading] [service] Run services with Docker
    stop [forecast|trading|metrics]           Stop application services
    test                             Run test suite with pytest
    --help [forecast|trading|metrics]        Show application-specific help

${GREEN}EXAMPLES:${NC}
    ${BLUE}# Forecast Application${NC}
    ./setup.sh init forecast
    ./setup.sh run-venv forecast all
    ./setup.sh stop forecast

    ${BLUE}# Trading Application${NC}
    ./setup.sh init trading
    ./setup.sh run-venv trading
    ./setup.sh stop trading

    ${BLUE}# Metrics Application${NC}
    ./setup.sh init metrics
    ./setup.sh run-venv metrics
    ./setup.sh stop metrics

    ${BLUE}# Help${NC}
    ./setup.sh --help forecast      # Help for forecast application
    ./setup.sh --help trading       # Help for trading application
    ./setup.sh --help metrics       # Help for metrics application

${GREEN}PORTS:${NC}
    - Forecast API: $API_PORT
    - Forecast UI: $UI_PORT
    - Trading API: $TRADING_PORT
    - Metrics API: $METRICS_PORT

${GREEN}REQUIREMENTS:${NC}
    - Bash shell
    - curl (for downloading UV)
    - Internet connection
    - Docker & Docker Compose (optional, for Docker deployment)

${GREEN}ENVIRONMENT:${NC}
    - Python Version: $PYTHON_VERSION
    - Virtual Environment: $VENV_NAME
    - Configuration: .env file

EOF
            ;;
    esac
}

# Main function
main() {
    case "${1:-}" in
        init)
            cmd_init "${2:-forecast}"  # Default to forecast for backward compatibility
            ;;
        run-venv)
            cmd_run_venv "${2:-}" "${3:-}"
            ;;
        run-docker)
            cmd_run_docker "${2:-}" "${3:-}"
            ;;
        test)
            cmd_test "${@:2}"
            ;;
        stop)
            cmd_stop "${2:-}"
            ;;
        --help|-h|help)
            show_help "${2:-}"
            ;;
        "")
            print_error "No command specified"
            echo
            show_help
            exit 1
            ;;
        *)
            print_error "Unknown command: $1"
            echo
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
