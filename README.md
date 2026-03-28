# Databox

A dataset-agnostic data platform for ingestion, transformation, quality checking, and visualization.

## Stack

- **dlt** — Python-native data ingestion with auto-schema detection
- **sqlmesh** — SQL-based transformations with version control and testing
- **DuckDB** — Embedded analytical database
- **Dagster** — Optional orchestration (scheduling, lineage, sensors)
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
├── cli/                     # `databox` CLI (Typer)
│   └── main.py
├── config/                  # Central configuration
│   ├── settings.py          # Pydantic settings (DB URL, paths, secrets)
│   ├── pipeline_config.py   # YAML config loader
│   └── pipelines/           # Per-pipeline configs
│       └── ebird.yaml
├── pipelines/               # dlt data ingestion
│   ├── base.py              # PipelineSource protocol
│   ├── registry.py          # Auto-discovery from config/pipelines/*.yaml
│   └── sources/
│       └── ebird_api.py
├── transformations/         # sqlmesh projects
│   ├── ebird/               # Per-source transform project
│   └── _shared/             # Shared macros, audits, seeds
├── orchestration/           # Dagster (optional)
│   └── dagster_project.py   # Auto-generated from registry
├── apps/                    # Visualization
│   └── ebird_streamlit/
├── data/                    # DuckDB database (gitignored)
│   └── databox.db
├── tests/                   # Test suite (70+ tests)
└── scripts/                 # Utility scripts
```

## Adding a New Data Source

1. Create `pipelines/sources/<source>.py` — implement `PipelineSource` protocol, expose `create_pipeline(config)` factory
2. Add `config/pipelines/<source>.yaml` — source module, schedule, params, quality rules
3. Create `transformations/<source>/` — sqlmesh project reading from `raw_<source>` schema
4. Add secrets to `.env`

No changes needed to CLI, orchestration, or Taskfile — they auto-discover from the registry.

## Development

```bash
task setup          # Setup environment
task test           # Run all tests
task test:unit      # Unit tests only
task test:e2e       # End-to-end tests
task lint           # Lint code
task format         # Format code
task streamlit      # Launch dashboard
```

## Testing

The test suite is dynamic — tests are parametrized from the pipeline registry so new sources get coverage automatically.

- **70 tests** covering config, registry, CLI, source protocol, e2e
- Schema-driven fake data factory generates test data from dlt column hints
- CLI tested via `typer.testing.CliRunner`
- Dagster tests skip gracefully if not installed

## License

MIT
