#!/bin/bash
# Setup pre-commit hooks for the project

echo "🔧 Setting up pre-commit hooks..."

# Check if we're in a virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    # Try to activate the local venv if it exists
    if [[ -f ".venv/bin/activate" ]]; then
        source .venv/bin/activate
    else
        echo "⚠️  No virtual environment found. Please activate your virtual environment first."
        exit 1
    fi
fi

# Install the pre-commit hooks
echo "🪝 Installing hooks..."
pre-commit install

# Run against all files to check current state
echo "🔍 Running initial check on all files..."
pre-commit run --all-files || true

echo "✅ Pre-commit hooks installed successfully!"
echo ""
echo "The following checks will run on every commit:"
echo "  - Trailing whitespace removal"
echo "  - End of file fixing"
echo "  - YAML/JSON/TOML validation"
echo "  - Python formatting (ruff)"
echo "  - Python linting (ruff)"
echo "  - Type checking (mypy)"
echo "  - 🔒 Secret detection"
echo ""
echo "To run checks manually: pre-commit run --all-files"
