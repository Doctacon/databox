# Databox

A dataset-agnostic data platform for ingestion, transformation, quality checking, and visualization.

## Stack

- **dlt** — Python-native data ingestion with auto-schema detection
- **sqlmesh** — SQL-based transformations with version control and testing
- **DuckDB** — Embedded analytical database
- **Dagster** — Orchestration (scheduling, lineage, sensors)
- **Soda Core** — Contract-based data quality checks
- **Typer CLI** — Unified `databox` command-line interface

## Quick Start

```bash
# Setup
task setup

# Configure API keys
cp .env.example .env
# Edit .env with your keys

# Run a pipeline
databox run ebird

# Transform data
databox transform plan
databox transform run

# Check status
databox status
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `databox list` | List registered pipelines |
| `databox run <name>` | Run a pipeline |
| `databox validate <name>` | Check pipeline config and credentials |
| `databox transform plan [project]` | Preview SQLMesh changes |
| `databox transform run [project]` | Apply SQLMesh transforms |
| `databox transform test [project]` | Run SQLMesh tests |
| `databox quality <schema.table>` | Data quality checks |
| `databox status` | Show pipeline status and data freshness |

## Project Structure

```
databox/
├── packages/                        # uv workspace monorepo
│   ├── databox-cli/                 # `databox` Typer CLI
│   ├── databox-config/              # Pydantic settings + YAML config loader
│   ├── databox-sources/             # dlt ingestion + per-source configs
│   │   └── databox_sources/
│   │       ├── base.py              # PipelineSource protocol
│   │       ├── registry.py          # Auto-discovers sources from config.yaml files
│   │       ├── ebird/               # eBird API (6 resources)
│   │       │   ├── config.yaml
│   │       │   └── source.py
│   │       └── noaa/                # NOAA CDO API (3 resources)
│   │           ├── config.yaml
│   │           └── source.py
│   ├── databox-orchestration/       # Dagster asset definitions (auto-generated)
│   └── databox-quality/             # Data quality engine (check_table, run_report)
├── transforms/
│   ├── main/                        # Single unified SQLMesh project (Postgres gateway)
│   │   └── models/
│   │       ├── ebird/               # staging → intermediate → marts
│   │       ├── noaa/                # staging → marts
│   │       └── analytics/           # cross-domain (bird + weather)
│   └── _shared/                     # Shared macros, audits, seeds
├── soda/
│   ├── datasources/                 # DuckDB connection config
│   └── contracts/                   # Data quality contracts (raw → staging → marts)
│       ├── raw_ebird/
│       ├── ebird_staging/
│       ├── ebird/
│       ├── raw_noaa/
│       ├── noaa_staging/
│       ├── noaa/
│       └── analytics/
├── app/                             # Streamlit DuckDB data explorer
├── docker/                          # Postgres init SQL
├── docker-compose.yml               # Postgres + Dagster services
├── data/                            # DuckDB database (gitignored)
│   └── databox.db
├── tests/                           # Test suite (10 files, 70+ tests)
└── scripts/                         # Utility scripts
```

## Data Sources

### eBird
- **API**: eBird API v2 (free, requires token)
- **Resources**: recent_observations, notable_observations, species_list, hotspots, taxonomy, region_stats
- **Transforms**: `raw_ebird` → staging → intermediate → marts + `analytics` cross-domain models

### NOAA CDO
- **API**: NOAA Climate Data Online v2 (free, requires token)
- **Resources**: daily_weather (TMAX/TMIN/PRCP/SNOW/AWND), stations, datasets
- **Transforms**: `raw_noaa` → staging → `noaa.fct_daily_weather`

## Adding a New Data Source

1. Create `packages/databox-sources/databox_sources/<source>/`
   - `source.py` — dlt source with `@dlt.source`/`@dlt.resource`, implements `PipelineSource`, exposes `create_pipeline(config)` factory
   - `config.yaml` — source module, schedule, params, quality rules

2. Add transform models at `transforms/main/models/<source>/`
   - Read from `raw_<source>.*` schemas (auto-created by dlt)
   - Write to `<source>.*` schema
   - Follow staging → marts layering pattern

3. Add secrets to `.env`: `API_KEY_<SOURCE>=your_key_here`

No changes needed to CLI, orchestration, or Taskfile — they auto-discover from the registry.

## Docker

```bash
# Start Postgres + Dagster
docker-compose up -d

# Dagster UI at http://localhost:3000
```

SQLMesh uses Postgres as the state gateway (defined in `transforms/main/config.yaml`). Default database is DuckDB at `data/databox.db`.

## Development

```bash
task setup          # Setup environment
task test           # Run all tests
task test:unit      # Unit tests only
task test:e2e       # End-to-end tests
task lint           # Lint code
task format         # Format code
task streamlit      # Launch data explorer
```

## Testing

Tests are parametrized from the pipeline registry — new sources get coverage automatically.

- 70+ tests covering config, registry, CLI, source protocol, Dagster, e2e
- Schema-driven fake data factory generates test data from dlt column hints
- CLI tested via `typer.testing.CliRunner`

## License

MIT
