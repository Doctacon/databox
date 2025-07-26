# Transformations Directory Guide

## Default SQLMesh Project Location

**⚠️ IMPORTANT: Use `home_team/` as the default location for all transformation models.**

## Directory Structure

```
transformations/
├── home_team/          # 🎯 DEFAULT PROJECT - Use this for all models
│   ├── models/
│   │   ├── staging/    # stg_ models - clean raw data
│   │   ├── intermediate/ # int_ models - business logic
│   │   └── marts/      # dim_/fct_ models - final analytics
│   ├── tests/          # Model tests
│   ├── audits/         # Data quality audits
│   ├── macros/         # Reusable SQL functions
│   ├── seeds/          # Static reference data
│   └── config.yaml     # SQLMesh configuration
├── away_team/          # Alternative project (rarely used)
└── CLAUDE.md          # This guide
```

## Model Development Workflow

### 1. Creating New Models
Always create models in `home_team/models/`:

```bash
# Staging models
home_team/models/staging/stg_[source]_[entity].sql

# Intermediate models  
home_team/models/intermediate/int_[business_process].sql

# Fact tables
home_team/models/marts/fct_[business_process].sql

# Dimension tables
home_team/models/marts/dim_[entity].sql
```

### 2. Model Naming Convention
Use the `sqlmesh_example` schema for all models:

```sql
MODEL (
  name sqlmesh_example.stg_ebird_observations,
  kind VIEW,
  description 'Clear description of the model purpose'
);
```

### 3. SQLMesh Commands
Run all SQLMesh commands from the `home_team/` directory:

```bash
cd transformations/home_team

# Plan changes
sqlmesh plan

# Apply transformations
sqlmesh run

# Run tests
sqlmesh test

# Start UI
sqlmesh ui
```

### 4. Database Configuration
The project uses DuckDB with the following connection in `config.yaml`:
- Database file: `db.db` (located in home_team/)
- Default gateway: `duckdb`
- Models run daily at 12am UTC (`@daily`)

## Best Practices

### Model Organization
1. **Staging**: Clean column names, handle nulls, add loaded_at timestamps
2. **Intermediate**: Join tables, apply business logic, calculate derived fields
3. **Marts**: Final models optimized for analytics and reporting

### Testing
- Add tests in `home_team/tests/`
- Test primary key uniqueness
- Validate not-null constraints
- Check business rule compliance

### Dependencies
- Raw data comes from dlt pipelines (schemas like `raw_ebird_data`)
- Models should reference upstream models, not raw tables directly
- Use CTEs for complex logic and readability

## Common Operations

### Adding eBird Models
The project includes example eBird models:
- `stg_ebird_observations.sql` - Clean bird observation data
- `stg_ebird_taxonomy.sql` - Species reference data
- `stg_ebird_hotspots.sql` - Birding location data
- `int_ebird_enriched_observations.sql` - Joined observations with taxonomy
- `fct_daily_bird_observations.sql` - Daily analytics facts

### CLI Integration
Use the databox CLI for transformations:
```bash
databox transform plan   # Preview changes
databox transform run    # Apply transformations
databox transform test   # Run all tests
databox transform ui     # Start web interface
```

## ⚠️ Important Notes

1. **Never create models outside of `home_team/`** unless explicitly required
2. **Always use the `sqlmesh_example` schema** for consistency
3. **Run SQLMesh commands from the `home_team/` directory**
4. **Follow the established naming conventions**
5. **Add tests for all new models**

This structure ensures consistency and makes the project maintainable for the entire team.