#!/bin/bash

# FABI+ PyPI Release Verification Script
# This script verifies that the FABI+ package was successfully published to PyPI

set -e

echo "🔍 FABI+ PyPI Release Verification"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create temporary directory for testing
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

print_status "Created temporary directory: $TEMP_DIR"

# Create virtual environment
print_status "Creating virtual environment..."
python3 -m venv test_env
source test_env/bin/activate

# Install fabiplus from PyPI
print_status "Installing fabiplus from PyPI..."
if pip install fabiplus; then
    print_success "Successfully installed fabiplus from PyPI"
else
    print_error "Failed to install fabiplus from PyPI"
    exit 1
fi

# Verify CLI is available
print_status "Verifying CLI availability..."
if command -v fabiplus &> /dev/null; then
    print_success "fabiplus CLI is available"
else
    print_error "fabiplus CLI not found in PATH"
    exit 1
fi

# Test version command
print_status "Testing version command..."
VERSION=$(fabiplus --version)
if [[ $? -eq 0 ]]; then
    print_success "Version command works: $VERSION"
else
    print_error "Version command failed"
    exit 1
fi

# Test help command
print_status "Testing help command..."
if fabiplus --help > /dev/null 2>&1; then
    print_success "Help command works"
else
    print_error "Help command failed"
    exit 1
fi

# Test project creation
print_status "Testing project creation..."
if fabiplus project startproject test_project --orm sqlmodel; then
    print_success "Project creation works"
else
    print_error "Project creation failed"
    exit 1
fi

# Verify project structure
print_status "Verifying project structure..."
if [[ -d "test_project" && -f "test_project/pyproject.toml" ]]; then
    print_success "Project structure is correct"
else
    print_error "Project structure is incorrect"
    exit 1
fi

# Test app creation
print_status "Testing app creation..."
cd test_project
if fabiplus app startapp test_app; then
    print_success "App creation works"
else
    print_error "App creation failed"
    exit 1
fi

# Verify app structure
print_status "Verifying app structure..."
if [[ -d "apps/test_app" && -f "apps/test_app/models.py" ]]; then
    print_success "App structure is correct"
else
    print_error "App structure is incorrect"
    exit 1
fi

# Clean up
print_status "Cleaning up..."
deactivate
cd /
rm -rf "$TEMP_DIR"

print_success "🎉 All verification tests passed!"
print_success "FABI+ is successfully published and working on PyPI"
print_success "Users can now install it with: pip install fabiplus"

echo ""
echo "📊 Verification Summary:"
echo "✅ Package installation from PyPI"
echo "✅ CLI availability and commands"
echo "✅ Project creation functionality"
echo "✅ App creation functionality"
echo "✅ File structure generation"
echo ""
echo "🚀 FABI+ is ready for production use!"
