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
hook_installed=true
if ! pre-commit install; then
    hook_installed=false
    echo "⚠️  Hook installation was skipped; check the repository's core.hooksPath setting."
fi

# Run against all files to check current state
echo "🔍 Running initial check on all files..."
pre-commit run --all-files || true

if [[ "$hook_installed" == "true" ]]; then
    echo "✅ Pre-commit hooks installed successfully!"
else
    echo "⚠️  Checks are configured, but the Git hook was not installed."
fi
echo ""
echo "The configured pre-commit checks are:"
echo "  - Trailing whitespace removal"
echo "  - End of file fixing"
echo "  - YAML/JSON/TOML validation"
echo "  - Python formatting (ruff)"
echo "  - Python linting (ruff)"
echo "  - 🔒 Secret detection"
echo ""
echo "To run checks manually: pre-commit run --all-files"
