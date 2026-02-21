#!/bin/bash
# Test runner script for Sapheneia

set -e

echo "==================================="
echo "Sapheneia Test Suite"
echo "==================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! python -m pytest --version > /dev/null 2>&1; then
    echo -e "${RED}Error: pytest not installed${NC}"
    echo "Install with: pip install pytest pytest-asyncio pytest-cov"
    exit 1
fi

# Parse arguments
QUICK=false
VERBOSE=false
COVERAGE_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --coverage)
            COVERAGE_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--quick] [--verbose] [--coverage]"
            exit 1
            ;;
    esac
done

# Run tests
if [ "$QUICK" = true ]; then
    echo -e "${YELLOW}Running quick tests (no coverage)...${NC}"
    python -m pytest tests/ -v --tb=short
elif [ "$COVERAGE_ONLY" = true ]; then
    echo -e "${YELLOW}Generating coverage report...${NC}"
    python -m pytest tests/ --cov=forecast/core --cov-report=html --cov-report=term-missing --cov-fail-under=90
else
    echo -e "${YELLOW}Running full test suite with coverage...${NC}"
    python -m pytest tests/ \
        -v \
        --cov=forecast/core \
        --cov-report=term-missing \
        --cov-report=html:htmlcov \
        --cov-fail-under=90
fi

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "Coverage report generated at: htmlcov/index.html"
    echo "Open with: open htmlcov/index.html"
    exit 0
else
    echo ""
    echo -e "${RED}❌ Tests failed${NC}"
    exit 1
fi
