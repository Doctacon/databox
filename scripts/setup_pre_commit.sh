#!/bin/bash
# Setup pre-commit hooks for the project

echo "🔧 Setting up pre-commit hooks..."

# Install pre-commit if not already installed
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
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
