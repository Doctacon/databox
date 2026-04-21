# Databox

[![CI](https://github.com/Doctacon/databox/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/Doctacon/databox/actions/workflows/ci.yaml)

A dataset-agnostic data platform for ingestion, transformation, quality checking, and visualization. Zero-infra local mode (file-based DuckDB) with a one-flag switch to MotherDuck cloud. Orchestrated end-to-end by Dagster.

## Stack

- **dlt** — Python-native data ingestion with auto-schema detection
- **sqlmesh** — SQL-based transformations with version control and testing
- **DuckDB** — Embedded analytical database (local) or MotherDuck (cloud)
- **Dagster** — Orchestration + unified entrypoint (assets, schedules, lineage, sensors)
- **Soda Core** — Contract-based data quality checks (run as asset checks)
- **Streamlit** — Data explorer app

## Quick Start

```bash
# Setup
task setup
task install

# Configure API keys
cp .env.example .env
# Edit .env — set EBIRD_API_TOKEN, NOAA_API_TOKEN

# Launch Dagster UI (http://localhost:3000)
task dagster:dev

# Or materialize everything headless (pipelines + transforms + quality checks)
task full-refresh

# Smoke test (limited ingest + last 3 days of transforms)
task verify
```

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

## Common Tasks

| Task | Description |
|------|-------------|
| `task dagster:dev` | Start Dagster UI (asset graph, run logs, schedules) |
| `task dagster:materialize` | Materialize every asset (full pipeline + transforms + quality) |
| `task full-refresh` | Alias for `dagster:materialize` |
| `task verify` | Smoke test: limited ingest + last 3 days of transforms |
| `task transform:plan` | `sqlmesh plan --auto-apply` in `transforms/main` |
| `task transform:run` | `sqlmesh run` |
| `task transform:test` | `sqlmesh test` |
| `task transform:ui` | SQLMesh UI |
| `task streamlit` | Launch Streamlit data explorer |
| `task db:reset` | Delete local DuckDB files |

Everything else (individual pipeline runs, quality checks, scheduling) happens through Dagster assets — one entrypoint, visible lineage, automatic retries.

## Project Structure

```
databox/
├── packages/                        # uv workspace monorepo
│   ├── databox-config/              # Pydantic settings + YAML config loader
│   ├── databox-sources/             # dlt ingestion + per-source configs
│   │   └── databox_sources/
│   │       ├── base.py              # PipelineSource protocol
│   │       ├── registry.py          # Auto-discovers sources from config.yaml
│   │       ├── ebird/               # eBird API
│   │       ├── noaa/                # NOAA CDO API
│   │       └── usgs/                # USGS NWIS Water Services
│   ├── databox-orchestration/       # Dagster asset definitions
│   └── databox-quality/             # Soda contract runner
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

No orchestration wiring needed — Dagster auto-discovers from the source registry.

## Development

```bash
task install        # Install dependencies
task verify         # Smoke test via Dagster
task lint           # Ruff lint
task format         # Ruff format
task typecheck      # mypy
task test           # pytest
```

See [docs/contracts.md](docs/contracts.md) for the schema-contract gate and the
`accept-breaking-change` escape hatch used on PRs that intentionally break
downstream consumers.

See [docs/incremental-loading.md](docs/incremental-loading.md) for the
per-resource write disposition, primary keys, idempotency guarantee, and
backfill commands.

See [docs/analytics-examples.md](docs/analytics-examples.md) for example
queries against the flagship cross-domain mart
(`analytics.fct_species_environment_daily`) that joins eBird observations
with NOAA weather and USGS streamflow at species × H3 cell × day grain.

## License

MIT
