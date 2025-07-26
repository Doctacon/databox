# Databox

A world-class data project using dlt for data ingestion and sqlmesh for data transformation.

## Features

- **Modern Data Stack**: Built with dlt (data load tool) and sqlmesh
- **Flexible Ingestion**: Support for APIs, CSV files, and more
- **SQL-First Transformations**: Powerful transformations using sqlmesh
- **Built-in Testing**: Data quality checks and transformation tests
- **Type Safety**: Full Python type hints and validation

## Quick Start

### 1. Setup Environment

This project uses [Task](https://taskfile.dev/) for development workflows. Install Task first:

```bash
# Clone the repository
git clone <your-repo-url>
cd databox

# Install Task (macOS)
brew install go-task/tap/go-task

# Complete environment setup
task setup

# Or just install dependencies
task install
```

### 2. Create Example Data

```bash
# Generate sample datasets
task setup-data
```

### 3. Run Data Pipelines

```bash
# List available pipelines
task pipeline:list

# Run the eBird API pipeline
task pipeline:ebird

# Run with specific region
task pipeline:ebird -- --region US-AZ
```

### 4. Transform Data

```bash
# Plan transformations (preview changes)
task transform:plan

# Apply transformations
task transform:run

# Run tests
task transform:test

# Open SQLMesh UI
task transform:ui
```

## Project Structure

```
databox/
├── pipelines/          # dlt data ingestion pipelines
├── transformations/    # sqlmesh transformation models
├── data/              # Data storage (gitignored)
├── orchestration/     # Dagster orchestration
├── scripts/           # Utility scripts
├── tests/             # Unit and integration tests
└── notebooks/         # Jupyter notebooks
```

## Architecture

### Data Flow

1. **Ingestion (dlt)**: Raw data is ingested from various sources into the `raw_` schemas
2. **Staging (sqlmesh)**: Data is cleaned and standardized in `stg_` models
3. **Intermediate (sqlmesh)**: Business logic is applied in `int_` models
4. **Marts (sqlmesh)**: Final analytical models are created as `dim_` and `fct_` tables

### Technology Stack

- **Database**: DuckDB (default, easily switchable)
- **Ingestion**: dlt (data load tool)
- **Transformation**: sqlmesh
- **Orchestration**: Dagster
- **Testing**: pytest + sqlmesh tests
- **Task Runner**: Task (go-task)
- **Package Manager**: uv (fast, reliable Python package management)

## Development

### Code Quality

```bash
# Format and lint code
task format
task lint

# Type checking
task typecheck

# Run all CI checks
task ci

# Check for secrets
task check-secrets
```

### Security

This project includes automatic security checks to prevent accidental commits of sensitive information:

- API keys, tokens, and passwords are detected and blocked
- Database URLs with credentials are flagged
- AWS keys and private keys are prevented from being committed

If you need to reference sensitive values:
1. Use environment variables: `os.environ.get("API_KEY")`
2. Use placeholder values: `"your_api_key_here"`

### Orchestration

```bash
# Start Dagster UI
task dagster:dev

# Run specific job
task dagster:job daily_ebird_pipeline

# Materialize assets
task dagster:materialize ebird_assets
```

## Configuration

All configuration is managed through environment variables in `.env`:

- `DATABASE_URL`: Database connection string
- `DLT_DATA_DIR`: Directory for dlt state
- `EBIRD_API_TOKEN`: eBird API token for data ingestion
- `LOG_LEVEL`: Logging verbosity

## Example Workflows

### Full Data Refresh
```bash
task full-refresh
```

### Multi-Region Data Loading
```bash
task pipeline:ebird -- --regions "US-AZ,US-NY,US-TX"
```

### SQLMesh Development
```bash
cd transformations/home_team
sqlmesh plan
sqlmesh run
```

## CI/CD

The project includes GitHub Actions workflows for:
- Code quality checks (linting, formatting, type checking)
- Security scanning
- SQLMesh model validation
- Dependency vulnerability scanning
- Automated testing

## License

MIT License - see LICENSE file for details.
