# Databox Project Guide

## Project Overview
Databox is a world-class data project that uses:
- **dlt (data load tool)** for flexible, Python-native data ingestion
- **sqlmesh** for powerful SQL-based data transformations with built-in testing and deployment
- **DuckDB** as the default analytical database (lightweight, fast, and perfect for development)

## Custom Slash Commands

### /dataops [operation]
Handles common data operations with dynamic parameters. Examples:
- `/dataops run ebird_api US-CA` - Run eBird pipeline for California
- `/dataops refresh` - Run all pipelines and transformations
- `/dataops check observations` - Data quality checks on specific table
- `/dataops status` - Show pipeline run history

### /sqlgen [model_type] [entity]
Generates SQL models with specific requirements. Examples:
- `/sqlgen staging ebird observations` - Create staging model from raw eBird data
- `/sqlgen fact daily bird sightings` - Create fact table for bird observation analytics
- `/sqlgen dimension species with taxonomy` - Create species dimension with taxonomic data
- `/sqlgen test dim_users` - Generate comprehensive tests for existing model

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

This project uses [Task](https://taskfile.dev/) for streamlined development workflows. Install Task first: `brew install go-task/tap/go-task`

### Environment Setup
```bash
# Complete development setup
task setup

# Install dependencies only
task install

# Install with development tools
task install-dev
```

### Running DLT Pipelines
```bash
# List available pipelines
task pipeline:list

# Run eBird API pipeline
task pipeline:ebird

# Run with custom parameters
task pipeline:ebird -- --region US-CA
```

### Working with SQLMesh
```bash
# Plan changes (preview what will change)
task transform:plan

# Apply changes
task transform:run

# Run tests
task transform:test

# Start UI
task transform:ui
```

### Development Commands
```bash
# Format and lint code
task format
task lint

# Type checking
task typecheck

# Run tests
task test

# Run tests with coverage
task test-coverage

# Run all CI checks
task ci
```

### Common Workflows
```bash
# Start development environment
task dev

# Complete data refresh
task full-refresh

# Clean build artifacts
task clean

# Reset everything
task clean-all

# Watch and auto-lint
task watch:lint

# Show all available tasks
task --list-all
```

## Best Practices

### DLT Pipeline Development
1. Keep pipelines modular - one source per file
2. Use incremental loading where possible
3. Implement proper error handling and retries
4. Store sensitive credentials in environment variables
5. Use dlt's built-in schema evolution features

### SQLMesh Model Development
1. **Always work in `home_team/` directory** - this is the default SQLMesh project
2. Use `sqlmesh_example` schema for all models
3. Use CTEs for readability
4. Write tests for critical business logic
5. Use macros for repeated patterns
6. Document models with descriptions
7. Follow naming conventions (stg_ for staging, int_ for intermediate, fct_ for facts, dim_ for dimensions)

### Data Quality
1. Implement data quality checks in both dlt and sqlmesh
2. Use dlt's data contracts for source validation
3. Use sqlmesh's audit features for transformation testing
4. Monitor data freshness and completeness

## Security

### Pre-commit Hooks
The project includes pre-commit hooks that automatically check for:
- Hardcoded secrets, API keys, and passwords
- Database URLs with embedded credentials
- AWS access keys and private keys
- Any other sensitive information patterns

To set up pre-commit hooks:
```bash
./scripts/setup_pre_commit.sh
```

### Handling Secrets
Never commit sensitive information. Instead:
1. Use environment variables via `.env` file
2. Reference settings: `settings.api_key`
3. Use placeholders in examples: `"your_api_key_here"`

## Common Tasks

### Adding a New Data Source
1. Create a new file in `pipelines/sources/`
2. Implement the source using dlt decorators
3. Add configuration to `.env`
4. Test the pipeline locally
5. Create corresponding sqlmesh models in `transformations/home_team/models/`

### Creating a Data Model
1. Create a new SQL file in `transformations/home_team/models/` (staging/, intermediate/, or marts/)
2. Use the `sqlmesh_example` schema name in MODEL definition
3. Define the model using sqlmesh syntax
4. Add tests in `transformations/home_team/tests/`
5. Run `sqlmesh plan` from `home_team/` directory to preview changes
6. Apply with `sqlmesh run`

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

## Memories
- No config or databox folders are necessary for users who know how to run transformations with `sqlmesh` and pipelines with `dlt`