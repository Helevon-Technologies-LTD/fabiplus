#!/bin/bash

# FABI+ Local CI Test Script
# This script runs the same checks as the GitHub Actions CI pipeline locally

set -e  # Exit on any error

echo "🚀 FABI+ Local CI Test Script"
echo "=============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2 passed${NC}"
    else
        echo -e "${RED}❌ $2 failed${NC}"
        return 1
    fi
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Error: pyproject.toml not found. Please run this script from the project root.${NC}"
    exit 1
fi

# Check Python version
echo -e "${YELLOW}🐍 Checking Python version...${NC}"
python_version=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if [[ "$python_version" < "3.10" ]]; then
    echo -e "${RED}❌ Python 3.10+ required. Current version: $python_version${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python version: $python_version${NC}"

# Check if Poetry is installed
echo -e "${YELLOW}📦 Checking Poetry installation...${NC}"
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}❌ Poetry not found. Please install Poetry first.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Poetry found: $(poetry --version)${NC}"

# Install dependencies
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
poetry install --no-interaction
print_status $? "Dependencies installation"

# Run code formatting checks
echo -e "${YELLOW}🎨 Running Black (code formatting)...${NC}"
poetry run black --check --diff fabiplus/ tests/ || {
    echo -e "${YELLOW}⚠️  Black formatting issues found. Run 'poetry run black fabiplus/ tests/' to fix.${NC}"
}

echo -e "${YELLOW}📋 Running isort (import sorting)...${NC}"
poetry run isort --check-only --diff fabiplus/ tests/ || {
    echo -e "${YELLOW}⚠️  Import sorting issues found. Run 'poetry run isort fabiplus/ tests/' to fix.${NC}"
}

# Run linting
echo -e "${YELLOW}🔍 Running flake8 (linting)...${NC}"
poetry run flake8 fabiplus/ tests/ || {
    echo -e "${YELLOW}⚠️  Linting issues found. Check output above.${NC}"
}

# Run type checking (non-blocking)
echo -e "${YELLOW}🔍 Running mypy (type checking)...${NC}"
poetry run mypy fabiplus/ || {
    echo -e "${YELLOW}⚠️  Type checking issues found (non-blocking).${NC}"
}

# Run security checks
echo -e "${YELLOW}🔒 Running Bandit (security linting)...${NC}"
poetry run bandit -r fabiplus/ -f json -o bandit-report.json || {
    echo -e "${YELLOW}⚠️  Security issues found. Check bandit-report.json${NC}"
}

echo -e "${YELLOW}🔒 Running Safety (dependency vulnerabilities)...${NC}"
poetry run safety scan --output json --save-as safety-report.json || {
    echo -e "${YELLOW}⚠️  Dependency vulnerabilities found. Check safety-report.json${NC}"
}

# Run tests
echo -e "${YELLOW}🧪 Running tests with coverage...${NC}"
poetry run pytest --cov=fabiplus --cov-report=xml --cov-report=html --cov-report=term-missing -v
print_status $? "Tests"

# Build package
echo -e "${YELLOW}📦 Building package...${NC}"
poetry build
print_status $? "Package build"

echo ""
echo -e "${GREEN}🎉 Local CI checks completed!${NC}"
echo ""
echo "📊 Reports generated:"
echo "  - bandit-report.json (security issues)"
echo "  - safety-report.json (dependency vulnerabilities)"
echo "  - coverage.xml (test coverage)"
echo "  - htmlcov/ (HTML coverage report)"
echo "  - dist/ (built packages)"
echo ""
echo "🔧 To fix formatting issues:"
echo "  poetry run black fabiplus/ tests/"
echo "  poetry run isort fabiplus/ tests/"
echo ""
echo "📚 To view coverage report:"
echo "  open htmlcov/index.html"
