# Databox Project Guide

## Project Overview
Databox is a dataset-agnostic data platform for a single operator, using zero-cost open-source tooling:
- **dlt (data load tool)** for flexible, Python-native data ingestion
- **sqlmesh** for SQL-based data transformations with built-in testing
- **DuckDB** as the analytical database (single file, no server)
- **Dagster** for orchestration (scheduling, sensors, asset lineage)
- **Typer CLI** (`databox`) for unified command-line interface
- **Streamlit** for a generic DuckDB data explorer

## Project Structure
```
databox/
├── cli/                     # `databox` CLI (Typer)
│   └── main.py              # Commands: run, list, validate, transform, quality, status
├── config/                  # Central configuration
│   ├── settings.py          # Pydantic settings (DB URL, paths, secrets)
│   └── pipeline_config.py   # Per-pipeline YAML config loader + QualityRule
├── sources/                 # dlt data ingestion + source configs
│   ├── base.py              # PipelineSource protocol
│   ├── registry.py          # Auto-discovers sources from sources/<name>/config.yaml
│   ├── ebird/
│   │   ├── config.yaml      # eBird pipeline config
│   │   └── source.py        # eBird dlt source (6 resources)
│   └── noaa/
│       ├── config.yaml      # NOAA pipeline config
│       └── source.py        # NOAA dlt source (daily_weather, stations, datasets)
├── transforms/              # sqlmesh projects
│   ├── ebird/               # eBird transforms (staging → intermediate → marts)
│   ├── noaa/                # NOAA transforms (staging + marts)
│   └── _shared/             # Shared macros, audits, seeds
├── quality/                 # Data quality engine
│   └── engine.py            # check_table() and run_report() pure functions
├── orchestration/           # Dagster orchestration
│   └── definitions.py       # Auto-generated from pipeline registry
├── app/                     # Generic DuckDB data explorer (Streamlit)
│   └── main.py
├── data/                    # Data storage (gitignored)
│   └── databox.db           # DuckDB database
└── scripts/                 # Utility scripts
```

## Key Commands

### CLI
```bash
databox list                              # List registered pipelines
databox run ebird                         # Run a pipeline
databox validate ebird                    # Check pipeline config/credentials
databox transform plan                    # Preview SQLMesh changes
databox transform run                     # Apply SQLMesh transforms
databox transform test                    # Run SQLMesh tests
databox quality check ebird.stg_ebird_observations  # Table quality checks
databox quality report                    # Run all configured quality rules
databox status                            # Show pipeline status & freshness
```

### Task
```bash
task setup                    # Setup environment
task install                  # Install dependencies
task pipeline:list            # List pipelines
task pipeline:run -- ebird    # Run a pipeline
task transform:plan           # SQLMesh plan
task transform:run            # SQLMesh run
task full-refresh             # Run everything
task streamlit                # Launch data explorer
```

## Data Sources

### eBird
- **API**: eBird API v2 (free, requires token)
- **Resources**: recent_observations, notable_observations, species_list, hotspots, taxonomy, region_stats
- **Transforms**: staging (observations, hotspots, taxonomy) → intermediate (enriched with taxonomy + haversine) → marts (daily bird observations)
- **Config**: `sources/ebird/config.yaml`

### NOAA CDO
- **API**: NOAA Climate Data Online v2 (free, requires token)
- **Resources**: daily_weather (TMAX/TMIN/PRCP/SNOW/AWND), stations, datasets
- **Transforms**: staging (daily_weather, stations) → marts (fct_daily_weather with pivoted metrics)
- **Config**: `sources/noaa/config.yaml`

## Adding a New Data Source

1. **Create source directory**: `sources/<source>/`
   - `source.py`: dlt resources using `@dlt.source` / `@dlt.resource`, a class implementing `PipelineSource`, and a `create_pipeline(config: PipelineConfig)` factory
   - `config.yaml`: pipeline config (see template below)

2. **Pipeline config template**: `sources/<source>/config.yaml`
   ```yaml
   source_module: "sources.<source>.source"
   description: "Description of the data source"
   schedule:
     cron: "0 6 * * *"
     enabled: true
   params:
     key: value
   quality_rules:
     - column: id
       check: not_null
     - column: status
       check: accepted_values
       values: ["active", "inactive"]
     - column: amount
       check: range
       threshold: 1000000
   transform_project: "<source>"
   ```

3. **Create transform project**: `transforms/<source>/`
   - Copy structure from `transforms/ebird/` as a template
   - Update `config.yaml` to point to `../../data/databox.db`
   - Read from `raw_<source>.*` schemas (auto-created by dlt)
   - Write to `<source>.*` schema

4. **Add secrets to `.env`**: `API_KEY_<SOURCE>=your_key_here`

5. **Test**: `databox run <source>` then `databox transform plan <source>`

No changes needed to orchestration, CLI, or Taskfile — they auto-discover from the registry.

## Data Quality Framework

Quality rules are defined per-source in `sources/<name>/config.yaml` and enforced by `databox quality report`.

Supported checks:
- **not_null**: Column must not contain NULLs
- **unique**: Column values must be unique
- **range**: Column must not exceed `threshold`
- **accepted_values**: Column must be one of `values` list

## Architecture Decisions

1. **Source Co-location**: Each source's config, ingestion code, and tests live together under `sources/<name>/`. The registry auto-discovers sources by scanning for `sources/*/config.yaml`.

2. **Per-Source Transforms**: Each data source gets its own sqlmesh project under `transforms/`. No cross-domain projects.

3. **Schema Isolation**: Pipelines load into `raw_<source>` schemas. Transforms read from `raw_*` and write to `<source>` schemas.

4. **Single Database**: One DuckDB at `data/databox.db`, configured in `config/settings.py`.

5. **Dynamic Orchestration**: Dagster assets are auto-generated from the pipeline registry. No hardcoded asset definitions.

6. **Generic Explorer**: The Streamlit app auto-discovers all schemas/tables from DuckDB. No per-source dashboards needed.

## Security

Never commit secrets. Use `.env` for API keys. Pre-commit hooks catch hardcoded values:
```bash
./scripts/setup_pre_commit.sh
```

## Memories
- This project only has a prod environment (no dev/docker-compose)
- Use `uv` for all package management
- dlt state lives in `.dlt_state/` at project root (not in `data/`)
- Dagster is a core dependency (not optional)
