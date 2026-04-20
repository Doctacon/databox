# Databox

A dataset-agnostic data platform for ingestion, transformation, quality checking, and visualization. Zero-infra local mode (file-based DuckDB) with a one-flag switch to MotherDuck cloud.

## Stack

- **dlt** — Python-native data ingestion with auto-schema detection
- **sqlmesh** — SQL-based transformations with version control and testing
- **DuckDB** — Embedded analytical database (local) or MotherDuck (cloud)
- **Dagster** — Orchestration (scheduling, lineage, sensors)
- **Soda Core** — Contract-based data quality checks
- **Typer CLI** — Unified `databox` command-line interface

## Quick Start

```bash
# Setup
task setup

# Configure API keys
cp .env.example .env
# Edit .env with your keys (EBIRD_API_TOKEN, NOAA_API_TOKEN)

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
| `databox transform plan` | Preview SQLMesh changes |
| `databox transform run` | Apply SQLMesh transforms |
| `databox transform test` | Run SQLMesh tests |
| `databox quality <schema.table>` | Data quality checks |
| `databox status` | Show pipeline status and data freshness |

## Backends

Switch between local and cloud via `.env`:

```bash
# Local (default) — file-based DuckDB, zero-infra
DATABOX_BACKEND=local
DATABOX_GATEWAY=local

# MotherDuck cloud
DATABOX_BACKEND=motherduck
DATABOX_GATEWAY=motherduck
MOTHERDUCK_TOKEN=<your_token>
```

`settings.database_path` and `settings.raw_*_path` are computed — they return `md:*` URIs for MotherDuck or local file paths otherwise.

## Project Structure

```
databox/
├── packages/                        # uv workspace monorepo
│   ├── databox-cli/                 # `databox` Typer CLI
│   ├── databox-config/              # Pydantic settings + YAML config loader
│   ├── databox-sources/             # dlt ingestion + per-source configs
│   │   └── databox_sources/
│   │       ├── base.py              # PipelineSource protocol
│   │       ├── registry.py          # Auto-discovers sources from config.yaml
│   │       ├── ebird/               # eBird API
│   │       ├── noaa/                # NOAA CDO API
│   │       └── usgs/                # USGS NWIS Water Services
│   ├── databox-orchestration/       # Dagster asset definitions
│   └── databox-quality/             # Data quality engine (Soda)
├── transforms/
│   └── main/                        # Unified SQLMesh project (duckdb dialect)
│       ├── config.yaml              # local + motherduck gateways
│       └── models/
│           ├── ebird/               # staging → intermediate → marts
│           ├── noaa/                # staging → marts
│           ├── usgs/                # staging → marts
│           └── analytics/           # cross-domain (bird + weather + streams)
├── soda/
│   ├── datasources/                 # DuckDB/MotherDuck connection config
│   └── contracts/                   # Data quality contracts per schema layer
├── app/                             # Streamlit data explorer
├── data/                            # DuckDB files (gitignored)
│   ├── databox.duckdb               # Transformed marts catalog
│   ├── raw_ebird.duckdb             # dlt landing zone (parallelized per source)
│   ├── raw_noaa.duckdb
│   └── raw_usgs.duckdb
└── scripts/                         # Utility scripts
```

### Schema Layering

```
raw_ebird / raw_noaa / raw_usgs        ← dlt loads (untouched API data)
ebird_staging / noaa_staging / usgs_staging  ← SQLMesh stg_* views (renames only)
ebird / noaa / usgs                    ← SQLMesh marts (fct_* / dim_*)
analytics                              ← cross-domain marts
```

Raw catalogs are split per-source DuckDB files so dlt can load in parallel.

## Data Sources

### eBird
- **API**: eBird API v2 (free, requires token)
- **Resources**: recent_observations, notable_observations, species_list, hotspots, taxonomy, region_stats
- **Transforms**: `raw_ebird` → `ebird_staging` → intermediate → `ebird.*` marts + `analytics` cross-domain

### NOAA CDO
- **API**: NOAA Climate Data Online v2 (free, requires token)
- **Resources**: daily_weather (TMAX/TMIN/PRCP/SNOW/AWND), stations, datasets
- **Transforms**: `raw_noaa` → `noaa_staging` → `noaa.fct_daily_weather`

### USGS Water Services
- **API**: NWIS Daily Values (no API key required)
- **Resources**: daily_values (discharge/gage height/water temp), sites
- **Transforms**: `raw_usgs` → `usgs_staging` → `usgs.fct_daily_streamflow`

## Adding a New Data Source

1. Create `packages/databox-sources/databox_sources/<source>/`
   - `source.py` — dlt source with `@dlt.source`/`@dlt.resource`, implements `PipelineSource`, exposes `create_pipeline(config)` factory
   - `config.yaml` — source module, schedule, params, quality rules

2. Add transform models at `transforms/main/models/<source>/`
   - Read from `raw_<source>.*` (auto-created by dlt)
   - Staging → `<source>_staging.*`, marts → `<source>.*`

3. Add Soda contracts at `soda/contracts/<source>_staging/` and `soda/contracts/<source>/`

4. Add secret to `.env`: `<SOURCE>_API_TOKEN=your_key_here`

No changes needed to CLI or orchestration — they auto-discover from the registry.

## Development

```bash
task setup          # Setup environment
task install        # Install dependencies
task verify         # Smoke test (dlt → SQLMesh → Soda)
task lint           # Lint code
task format         # Format code
task streamlit      # Launch data explorer
```

## License

MIT
