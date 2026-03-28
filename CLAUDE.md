# Databox Project Guide

## Project Overview
Databox is a dataset-agnostic data platform that uses:
- **dlt (data load tool)** for flexible, Python-native data ingestion
- **sqlmesh** for SQL-based data transformations with built-in testing
- **DuckDB** as the default analytical database
- **Dagster** for optional orchestration (scheduling, sensors, asset lineage)
- **Typer CLI** (`databox`) for unified command-line interface

## Project Structure
```
databox/
├── cli/                     # `databox` CLI (Typer)
│   └── main.py              # Commands: run, list, validate, transform, quality, status
├── config/                  # Central configuration
│   ├── settings.py          # Pydantic settings (DB URL, paths, secrets)
│   ├── pipeline_config.py   # Per-pipeline YAML config loader
│   └── pipelines/           # Pipeline YAML configs
│       └── ebird.yaml       # eBird pipeline config
├── pipelines/               # dlt data ingestion
│   ├── base.py              # PipelineSource protocol
│   ├── registry.py          # Auto-discovers sources from config/pipelines/*.yaml
│   └── sources/             # Source implementations
│       └── ebird_api.py     # eBird source (implements PipelineSource)
├── transformations/         # sqlmesh projects
│   ├── ebird/               # eBird-specific sqlmesh project
│   │   ├── config.yaml
│   │   └── models/
│   │       ├── staging/
│   │       ├── intermediate/
│   │       └── marts/
│   ├── home_team/           # Cross-domain analytics layer
│   └── _shared/             # Shared macros, audits, seeds
├── orchestration/           # Dagster (optional)
│   └── dagster_project.py   # Auto-generated from pipeline registry
├── apps/                    # Visualization
│   └── ebird_streamlit/
├── data/                    # Data storage (gitignored)
│   ├── databox.db           # DuckDB database
│   └── dlt/                 # dlt state
└── scripts/                 # Utility scripts
```

## Key Commands

### CLI (preferred)
```bash
databox list                  # List registered pipelines
databox run ebird             # Run a pipeline
databox validate ebird        # Check pipeline config/credentials
databox transform plan        # Preview SQLMesh changes
databox transform run         # Apply SQLMesh transforms
databox transform test        # Run SQLMesh tests
databox quality ebird.stg_ebird_observations  # Data quality checks
databox status                # Show pipeline status & freshness
```

### Task (alternative)
```bash
task setup                    # Setup environment
task install                  # Install dependencies
task pipeline:list            # List pipelines
task pipeline:run -- ebird    # Run a pipeline
task transform:plan           # SQLMesh plan
task transform:run            # SQLMesh run
task full-refresh             # Run everything
task ci                       # All CI checks
```

## Adding a New Data Source

1. **Create source module**: `pipelines/sources/<source>.py`
   - Define dlt resources using `@dlt.source` / `@dlt.resource`
   - Create a class implementing the `PipelineSource` protocol (`name`, `config`, `resources()`, `load()`, `validate_config()`)
   - Expose a `create_pipeline(config: PipelineConfig)` factory function

2. **Add pipeline config**: `config/pipelines/<source>.yaml`
   ```yaml
   source_module: "pipelines.sources.<source>"
   description: "Description of the data source"
   schedule:
     cron: "0 6 * * *"
     enabled: true
   params:
     key: value
   quality_rules:
     - column: id
       check: not_null
   transform_project: "<source>"
   ```

3. **Create transform project**: `transformations/<source>/`
   - Copy structure from `transformations/ebird/` as a template
   - Update `config.yaml` to point to `../../data/databox.db`
   - Read from `raw_<source>.*` schemas (auto-created by dlt)
   - Write to `<source>.*` schema

4. **Add secrets to `.env`**: `API_KEY_<SOURCE>=your_key_here`

5. **Test**: `databox run <source>` then `databox transform plan <source>`

No changes needed to orchestration, CLI, or Taskfile — they auto-discover from the registry.

## Architecture Decisions

1. **Pipeline Registry**: Sources auto-discovered from `config/pipelines/*.yaml`. Each config points to a source module that implements `PipelineSource`.

2. **Per-Source Transforms**: Each data source gets its own sqlmesh project under `transformations/`. `home_team/` is reserved for cross-domain models.

3. **Schema Isolation**: Pipelines load into `raw_<source>` schemas. Transforms read from `raw_*` and write to `<source>` schemas.

4. **Single Database**: One DuckDB at `data/databox.db`, configured in `config/settings.py`.

5. **Dynamic Orchestration**: Dagster assets are auto-generated from the pipeline registry. No hardcoded asset definitions.

## Security

Never commit secrets. Use `.env` for API keys. Pre-commit hooks catch hardcoded values:
```bash
./scripts/setup_pre_commit.sh
```

## Memories
- This project only has a prod environment (no dev/docker-compose)
- Use `uv` for all package management
