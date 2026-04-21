# Configuration

Databox has one authoritative runtime-config surface:
[`packages/databox/databox/config/settings.py`](https://github.com/Doctacon/databox/blob/main/packages/databox/databox/config/settings.py).
The `DataboxSettings` Pydantic object owns every runtime knob. Every
other file imports it rather than re-declaring values or calling
`os.getenv` directly.

## Authoritative surface

| Setting | Env var | Source | Notes |
|---|---|---|---|
| Backend | `DATABOX_BACKEND` | `settings.backend` | `local` (default) or `motherduck` |
| MotherDuck token | `MOTHERDUCK_TOKEN` | `settings.motherduck_token` | Required when backend = `motherduck` |
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
| `settings.raw_ebird_path` | `"md:raw_ebird"` on motherduck, `data/raw_ebird.duckdb` otherwise |
| `settings.raw_noaa_path` | `"md:raw_noaa"` on motherduck, `data/raw_noaa.duckdb` otherwise |
| `settings.raw_usgs_path` | `"md:raw_usgs"` on motherduck, `data/raw_usgs.duckdb` otherwise |
| `settings.soda_datasource_yaml` | Rendered Soda datasource YAML using `database_path` |
| `settings.sqlmesh_config()` | A `sqlmesh.core.config.Config` with both gateways and `default_gateway` = current backend |

## Where it's read

- **SQLMesh** — `transforms/main/config.py` returns `settings.sqlmesh_config()`; SQLMesh auto-discovers this Python config file in place of a `config.yaml`.
- **Dagster** — `packages/databox/databox/orchestration/definitions.py` reads `settings.backend`, `settings.gateway`, `settings.raw_*_path`, `settings.dlt_data_dir`, `settings.days_back(...)`, and `settings.soda_datasource_yaml`.
- **Streamlit explorer** — `app/main.py` uses `settings.database_path`.
- **Data-dictionary generator** — `scripts/generate_docs.py` uses `settings.gateway`.

## Out-of-surface configuration

Two classes of config live outside `DataboxSettings` on purpose:

- **Per-source API tokens** (`EBIRD_API_TOKEN`, `NOAA_API_TOKEN`) are read at call time in `databox_sources/*/source.py`. Leaving them on `os.getenv` lets dlt's own config system and pytest's `monkeypatch.setenv` work cleanly. Migrating secrets off `.env` is tracked by `ticket:secrets-pluggable`.
- **Build metadata in `pyproject.toml`** (package names, deps, Ruff/mypy config) is not runtime config.

## Switching backends

```bash
# Local (default)
DATABOX_BACKEND=local

# MotherDuck
DATABOX_BACKEND=motherduck
MOTHERDUCK_TOKEN=<token>
```

Flipping `DATABOX_BACKEND` flips SQLMesh's gateway, Dagster's dlt
destinations, and Soda's datasource connection without touching any
other file.
