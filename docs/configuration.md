# Configuration

Databox has one authoritative runtime-config surface:
[`packages/databox/databox/config/settings.py`](https://github.com/Doctacon/databox/blob/main/packages/databox/databox/config/settings.py).
The `DataboxSettings` Pydantic object owns every runtime knob. Every
other file imports it rather than re-declaring values or calling
`os.getenv` directly.

## Authoritative surface

| Setting | Env var | Source | Notes |
|---|---|---|---|
| Backend | `DATABOX_BACKEND` | `settings.backend` | `quack` (default), `local` (legacy per-source files), or `motherduck` |
| MotherDuck token | `MOTHERDUCK_TOKEN` | `settings.motherduck_token` | Required when backend = `motherduck` |
| Quack URI | `DATABOX_QUACK_URI` | `settings.quack_uri` | Default `quack:localhost:9494` |
| Quack token | `DATABOX_QUACK_TOKEN` | `settings.quack_token` | Default local token for Quack clients |
| Log level | `LOG_LEVEL` | `settings.log_level` | Default `INFO` |
| Smoke mode | `DATABOX_SMOKE` | `settings.smoke` | Boolean; limits dlt sources for fast runs |
| eBird window | `DATABOX_EBIRD_DAYS_BACK` | `settings.ebird_days_back` | Default 30 |
| NOAA window | `DATABOX_NOAA_DAYS_BACK` | `settings.noaa_days_back` | Default 30 |
| USGS window | `DATABOX_USGS_DAYS_BACK` | `settings.usgs_days_back` | Default 30 |

## Derived values

The following are `@computed_field` properties on `DataboxSettings` —
consumers read them, nothing sets them directly.

| Derived value | Expression |
|---|---|
| `settings.gateway` | `"motherduck" if backend == "motherduck" else "local"` |
| `settings.database_path` | `"md:databox"` on motherduck, `data/databox.duckdb` otherwise |
| `settings.raw_catalog_path(name)` | `data/databox.duckdb` on quack, `"md:raw_<name>"` on motherduck, `data/raw_<name>.duckdb` on legacy local |
| `settings.raw_dataset_name(name)` | `raw_<name>` on quack, `main` on motherduck and legacy local per-source files |
| `settings.motherduck_database_names` | List of every MotherDuck database the stack expects (derived from the source registry) |
| `settings.soda_datasource_yaml` | Rendered Soda datasource YAML using `database_path` |
| `settings.sqlmesh_config()` | A `sqlmesh.core.config.Config` with the active gateway and `default_gateway` = current backend |

## Where it's read

- **SQLMesh** — `transforms/main/config.py` returns `settings.sqlmesh_config()`; SQLMesh auto-discovers this Python config file in place of a `config.yaml`.
- **Dagster dlt ingest assets** — each source ingest job starts a local Quack server over `settings.database_path`, runs that one dlt source into its physical `raw_<source>` schema, stops Quack, and deduplicates append-loaded raw tables.
- **Dagster** — `packages/databox/databox/orchestration/definitions.py` reads `settings.backend`, `settings.gateway`, `settings.raw_catalog_path(...)`, `settings.raw_dataset_name(...)`, `settings.dlt_data_dir`, `settings.days_back(...)`, and `settings.soda_datasource_yaml`.
- **Streamlit explorer** — `app/main.py` uses `settings.database_path`.
- **Data-dictionary generator** — `scripts/generate_docs.py` uses `settings.gateway`.

## Out-of-surface configuration

Two classes of config live outside `DataboxSettings` on purpose:

- **Per-source API tokens** (`EBIRD_API_TOKEN`, `NOAA_API_TOKEN`) are read at call time in `databox_sources/*/source.py`. Leaving them on `os.getenv` lets dlt's own config system and pytest's `monkeypatch.setenv` work cleanly. Migrating secrets off `.env` is tracked by `ticket:secrets-pluggable`.
- **Build metadata in `pyproject.toml`** (package names, deps, Ruff/mypy config) is not runtime config.

## SQLMesh state

`sqlmesh_config()` points SQLMesh at a dedicated state DB
(`data/sqlmesh_state.duckdb`) via `GatewayConfig.state_connection`, separate
from the data catalogs. Both the local and MotherDuck gateways use this local
file for state.

Why it's split out:

- The data-catalog connection loads the `h3` DuckDB extension. SQLMesh's state
  pool opens the same file without extensions, which DuckDB refuses with
  *"Can't open a connection to same database file with a different
  configuration than existing connections."*
- SQLMesh explicitly warns against using MotherDuck as the state backend for
  production deployments. Keeping state on a local file satisfies that guidance
  without adding infrastructure (e.g., a Postgres state store).

`task db:reset` removes `data/sqlmesh_state.duckdb` alongside the catalog files
so a reset leaves no orphan state.

## Switching backends

```bash
# Quack local (default): all dlt sources write to data/databox.duckdb
DATABOX_BACKEND=quack

# Legacy local: per-source raw_*.duckdb files
DATABOX_BACKEND=local

# MotherDuck
DATABOX_BACKEND=motherduck
MOTHERDUCK_TOKEN=<token>
```

Flipping `DATABOX_BACKEND` flips SQLMesh's gateway, dlt destinations,
raw dataset naming, and Soda's datasource connection without touching any
other file. `task full-refresh` and `task verify` force `DATABOX_BACKEND=quack`
for both Dagster ingest jobs and the native SQLMesh prod restatement so stale
local `.env` files do not silently take the old path.
