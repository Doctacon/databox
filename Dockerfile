# Use official Python runtime as base image
FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV=/app/.venv

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Create non-root user for security
RUN groupadd -r databox && useradd -r -g databox databox

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock* ./

# Create virtual environment and install all dependencies
RUN uv venv /app/.venv && \
    uv pip install --no-cache -e . && \
    uv pip install --no-cache pytest pytest-cov mypy types-requests

# Copy application code
COPY . .

# Change ownership to non-root user
RUN chown -R databox:databox /app

# Switch to non-root user
USER databox

# Create necessary directories
RUN mkdir -p data/dlt data/raw data/staging data/processed logs notebooks

# Default command (can be overridden)
CMD ["python", "-m", "dagster", "dev", "-f", "orchestration/dagster_project.py", "-h", "0.0.0.0", "-p", "3000"]