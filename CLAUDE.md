# Databox Project Guide

## Project Overview
Databox is a world-class data project that uses:
- **dlt (data load tool)** for flexible, Python-native data ingestion
- **sqlmesh** for powerful SQL-based data transformations with built-in testing and deployment
- **DuckDB** as the default analytical database (lightweight, fast, and perfect for development)

## Project Structure
```
databox/
├── pipelines/          # dlt data ingestion pipelines
│   ├── sources/       # Data source implementations
│   └── destinations/  # Custom destination configurations
├── transformations/    # sqlmesh project root
│   ├── models/        # SQL transformation models
│   ├── tests/         # Model tests
│   ├── macros/        # Reusable SQL macros
│   └── seeds/         # Static reference data
├── data/              # Data storage (gitignored)
│   ├── raw/           # Raw ingested data
│   ├── staging/       # Intermediate transformations
│   ├── processed/     # Final analytical tables
│   └── dlt/           # dlt internal state
├── config/            # Configuration management
├── scripts/           # Utility scripts
├── tests/             # Python tests
├── docs/              # Documentation
└── notebooks/         # Jupyter notebooks for analysis
```

## Key Commands

### Environment Setup
```bash
# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

### Running DLT Pipelines
```bash
# Run a specific pipeline
python pipelines/sources/example_pipeline.py

# Run with custom configuration
DLT_DATA_DIR=./custom_data python pipelines/sources/example_pipeline.py
```

### Working with SQLMesh
```bash
# Initialize sqlmesh project (already done)
cd transformations
sqlmesh init

# Create a new model
sqlmesh create_model <model_name>

# Plan changes (preview what will change)
sqlmesh plan

# Apply changes
sqlmesh run

# Run tests
sqlmesh test

# Start UI
sqlmesh ui
```

### Development Commands
```bash
# Format code
black .
ruff check . --fix

# Type checking
mypy databox/

# Run tests
pytest

# Run tests with coverage
pytest --cov=databox --cov-report=html
```

## Best Practices

### DLT Pipeline Development
1. Keep pipelines modular - one source per file
2. Use incremental loading where possible
3. Implement proper error handling and retries
4. Store sensitive credentials in environment variables
5. Use dlt's built-in schema evolution features

### SQLMesh Model Development
1. Use CTEs for readability
2. Write tests for critical business logic
3. Use macros for repeated patterns
4. Document models with descriptions
5. Follow naming conventions (stg_ for staging, int_ for intermediate, fct_ for facts, dim_ for dimensions)

### Data Quality
1. Implement data quality checks in both dlt and sqlmesh
2. Use dlt's data contracts for source validation
3. Use sqlmesh's audit features for transformation testing
4. Monitor data freshness and completeness

## Common Tasks

### Adding a New Data Source
1. Create a new file in `pipelines/sources/`
2. Implement the source using dlt decorators
3. Add configuration to `.env`
4. Test the pipeline locally
5. Create corresponding sqlmesh models in `transformations/models/`

### Creating a Data Model
1. Create a new SQL file in `transformations/models/`
2. Define the model using sqlmesh syntax
3. Add tests in `transformations/tests/`
4. Run `sqlmesh plan` to preview changes
5. Apply with `sqlmesh run`

### Debugging Issues
- Check logs in `logs/` directory
- Use `dlt pipeline <name> trace` for detailed dlt debugging
- Use `sqlmesh audit` for model validation
- Check `.dlt/` directory for pipeline state

## Architecture Decisions

1. **DuckDB as Default Database**: Chosen for simplicity, performance, and zero dependencies. Easy to switch to PostgreSQL/Snowflake later.

2. **Separation of Ingestion and Transformation**: Clear boundaries between raw data (dlt) and business logic (sqlmesh).

3. **Environment-based Configuration**: All settings configurable via environment variables for easy deployment.

4. **Type Safety**: Using Pydantic for configuration and mypy for static typing.

## Future Enhancements
- Add Airflow/Dagster for orchestration
- Implement data catalog with DataHub/OpenMetadata
- Add real-time streaming capabilities
- Set up CI/CD pipeline for automated testing and deployment
- Add data visualization layer with Streamlit/Dash

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure you've installed the package with `pip install -e .`
2. **Database Connection**: Check DATABASE_URL in .env
3. **Permission Errors**: Ensure data directories have write permissions
4. **Memory Issues**: Adjust DuckDB memory settings or batch sizes

### Getting Help
- dlt documentation: https://dlthub.com/docs
- sqlmesh documentation: https://sqlmesh.com/
- DuckDB documentation: https://duckdb.org/docs/