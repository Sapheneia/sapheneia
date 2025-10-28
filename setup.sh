#!/bin/bash

# =============================================================================
# Sapheneia FastAPI Setup Script
#
# This script manages the Sapheneia FastAPI application with multiple options:
# - Initialize environment and dependencies
# - Run API and/or UI with virtual environment
# - Run API and/or UI with Docker
#
# Usage:
#   ./setup.sh init              # Initialize environment
#   ./setup.sh run-venv api      # Run API with venv
#   ./setup.sh run-venv ui       # Run UI with venv
#   ./setup.sh run-venv all      # Run both API and UI
#   ./setup.sh run-docker api    # Run API with Docker
#   ./setup.sh run-docker ui     # Run UI with Docker
#   ./setup.sh run-docker all    # Run both with Docker Compose
#   ./setup.sh stop              # Stop all running services
#   ./setup.sh --help            # Show help
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
    print_header "Initializing Sapheneia Environment"

    # Check if we're in the right directory
    if [[ ! -f "pyproject.toml" ]]; then
        print_error "Please run this script from the sapheneia project root directory"
        print_error "Expected file: pyproject.toml"
        exit 1
    fi

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
    mkdir -p api/models/timesfm20/local
    mkdir -p data/uploads
    mkdir -p data/results
    mkdir -p logs

    print_header "Initialization Complete!"
    print_status "Sapheneia environment is ready!"
    echo
    print_status "Next steps:"
    echo "  1. Edit .env file and set your API_SECRET_KEY"
    echo "  2. Run API: ./setup.sh run-venv api"
    echo "  3. Run UI: ./setup.sh run-venv ui"
    echo "  4. Or run both: ./setup.sh run-venv all"
    echo "  5. Run tests: ./setup.sh test"
    echo
}

# Function to run API with venv
run_api_venv() {
    print_header "Starting API Server (Virtual Environment)"

    kill_port $API_PORT

    print_status "Starting API on port $API_PORT..."
    uv run uvicorn api.main:app --host 0.0.0.0 --port $API_PORT --reload &

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

# Function to run with venv
cmd_run_venv() {
    local service=$1

    if [[ ! -d "$VENV_NAME" ]]; then
        print_error "Virtual environment not found. Run: ./setup.sh init"
        exit 1
    fi

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
            print_header "All Services Started"
            print_status "API: http://localhost:$API_PORT"
            print_status "UI: http://localhost:$UI_PORT"
            echo
            print_status "Press Ctrl+C to stop (servers run in background)"
            print_status "To stop all: ./setup.sh stop"
            ;;
        *)
            print_error "Unknown service: $service"
            print_error "Usage: ./setup.sh run-venv [api|ui|all]"
            exit 1
            ;;
    esac
}

# Function to run with Docker
cmd_run_docker() {
    local service=$1

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

    case $service in
        api)
            print_status "Building and starting API container..."
            $COMPOSE_CMD up -d api
            sleep 3
            print_status "✅ API running at http://localhost:$API_PORT"
            ;;
        ui)
            print_status "Building and starting UI container..."
            $COMPOSE_CMD up -d ui
            sleep 3
            print_status "✅ UI running at http://localhost:$UI_PORT"
            ;;
        all)
            print_status "Building and starting all containers..."
            $COMPOSE_CMD up -d
            sleep 5
            print_status "✅ API running at http://localhost:$API_PORT"
            print_status "✅ UI running at http://localhost:$UI_PORT"
            echo
            print_status "View logs: $COMPOSE_CMD logs -f"
            print_status "To stop: ./setup.sh stop"
            ;;
        *)
            print_error "Unknown service: $service"
            print_error "Usage: ./setup.sh run-docker [api|ui|all]"
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

# Function to stop all services
cmd_stop() {
    print_header "Stopping All Services"

    # Stop Docker services
    if command_exists docker; then
        print_status "Stopping Docker containers..."
        # Stop and remove containers by name
        docker stop sapheneia-api sapheneia-ui 2>/dev/null || true
        docker rm sapheneia-api sapheneia-ui 2>/dev/null || true
        print_status "Docker containers stopped and removed"
    fi

    print_status "Stopping venv ports..."
    # Stop venv services
    kill_port $API_PORT
    kill_port $UI_PORT

    print_status "✅ All services stopped"
}

# Function to show help
show_help() {
    cat << EOF
${BLUE}Sapheneia FastAPI Setup Script${NC}

${GREEN}USAGE:${NC}
    ./setup.sh COMMAND [OPTIONS]

${GREEN}COMMANDS:${NC}
    init                      Initialize environment and install dependencies (including tests)
    run-venv [api|ui|all]    Run services with virtual environment
    run-docker [api|ui|all]  Run services with Docker
    test                      Run test suite with pytest
    stop                      Stop all running services
    --help, -h               Show this help message

${GREEN}EXAMPLES:${NC}
    ${BLUE}# Initialize environment${NC}
    ./setup.sh init

    ${BLUE}# Run with virtual environment${NC}
    ./setup.sh run-venv api      # Run only API server
    ./setup.sh run-venv ui       # Run only UI server
    ./setup.sh run-venv all      # Run both API and UI

    ${BLUE}# Run with Docker${NC}
    ./setup.sh run-docker api    # Run only API container
    ./setup.sh run-docker ui     # Run only UI container
    ./setup.sh run-docker all    # Run both with Docker Compose

    ${BLUE}# Run tests${NC}
    ./setup.sh test              # Run test suite

    ${BLUE}# Stop all services${NC}
    ./setup.sh stop

${GREEN}REQUIREMENTS:${NC}
    - Bash shell
    - curl (for downloading UV)
    - Internet connection
    - Docker & Docker Compose (optional, for Docker deployment)

${GREEN}PORTS:${NC}
    - API Server: $API_PORT
    - UI Server: $UI_PORT

${GREEN}ENVIRONMENT:${NC}
    - Python Version: $PYTHON_VERSION
    - Virtual Environment: $VENV_NAME
    - Configuration: .env file

EOF
}

# Main function
main() {
    case "${1:-}" in
        init)
            cmd_init
            ;;
        run-venv)
            cmd_run_venv "${2:-}"
            ;;
        run-docker)
            cmd_run_docker "${2:-}"
            ;;
        test)
            cmd_test "${@:2}"
            ;;
        stop)
            cmd_stop
            ;;
        --help|-h|help)
            show_help
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
