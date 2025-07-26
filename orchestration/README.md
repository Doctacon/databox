# Databox Orchestration with Dagster

This directory contains the Dagster orchestration setup for the Databox project.

## Overview

Dagster is used to orchestrate data pipelines, providing:
- Visual pipeline monitoring
- Scheduling and sensors
- Asset lineage tracking
- Built-in observability

## Structure

- `dagster_project.py` - Main Dagster definitions including:
  - **Assets**: DLT ingestion and SQLMesh transformations
  - **Jobs**: Pipeline orchestration
  - **Schedules**: Automated pipeline runs
  - **Sensors**: Event-driven pipeline triggers
  - **Resources**: Shared configuration and connections

## Key Components

### Assets
1. **ebird_assets** - Ingests eBird data using DLT
2. **sqlmesh_staging** - Runs SQLMesh transformations
3. **data_quality_checks** - Validates data quality

### Jobs
- **daily_ebird_pipeline** - Complete ETL pipeline for eBird data

### Schedules
- **daily_ebird_schedule** - Runs pipeline daily at 6 AM

### Sensors
- **ebird_api_availability_sensor** - Checks API availability before running

## Getting Started

### Local Development

```bash
# Install Dagster dependencies
uv pip install dagster dagster-webserver dagster-dlt dagster-duckdb

# Launch Dagster UI
task dagster:dev

# Or manually:
cd orchestration
dagster dev -f dagster_project.py
```

### Production Deployment

```bash
# Generate Dagster workspace
dagster project scaffold --name databox-orchestration

# Deploy to Dagster Cloud or self-hosted
dagster deploy
```

## Configuration

Set these environment variables:
- `EBIRD_API_TOKEN` - Your eBird API token
- `DATABASE_URL` - Database connection string
- `DLT_DATA_DIR` - Directory for DLT state

## Testing

```bash
# Test job execution
dagster job execute -f dagster_project.py -j daily_ebird_pipeline

# Test specific asset
dagster asset materialize -f dagster_project.py --asset ebird_assets
```

## Monitoring

Access the Dagster UI at http://localhost:3000 to:
- View asset lineage
- Monitor pipeline runs
- Check logs and metrics
- Manage schedules

## Best Practices

1. **Idempotency**: All assets are designed to be re-run safely
2. **Partitioning**: Consider adding time-based partitions for historical data
3. **Testing**: Test assets individually before full pipeline runs
4. **Resources**: Share resources across assets for consistency
