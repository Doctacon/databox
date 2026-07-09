# Configuration

Databox has one authoritative runtime-config surface:
[`packages/databox/databox/config/settings.py`](https://github.com/Doctacon/databox/blob/main/packages/databox/databox/config/settings.py).
The `DataboxSettings` Pydantic object owns every runtime knob. Other runtime
code imports it rather than redeclaring values.

## Authoritative surface

| Setting | Env var | Source | Notes |
|---|---|---|---|
| Quack URI | `DATABOX_QUACK_URI` | `settings.quack_uri` | Default `quack:localhost:9494` |
| Quack token | `DATABOX_QUACK_TOKEN` | `settings.quack_token` | Local client/server token |
| Log level | `LOG_LEVEL` | `settings.log_level` | Default `INFO` |
| Smoke mode | `DATABOX_SMOKE` | `settings.smoke` | Limits source rows for verification |
| eBird window | `DATABOX_EBIRD_DAYS_BACK` | `settings.ebird_days_back` | Default 30 |
| NOAA window | `DATABOX_NOAA_DAYS_BACK` | `settings.noaa_days_back` | Default 30 |
| USGS window | `DATABOX_USGS_DAYS_BACK` | `settings.usgs_days_back` | Default 30 |
| OpenLineage URL | `OPENLINEAGE_URL` | `settings.openlineage_url` | Optional; disabled when unset |
| Workers AI API key | `CF_WORKERS_AI_API_KEY` | `settings.cf_workers_ai_api_key` | Secret; required for trip-plan synthesis |
| Workers AI account | `CF_WORKERS_AI_ACCOUNT_ID` | `settings.cf_workers_ai_account_id` | Required for trip-plan synthesis |
| Workers AI endpoint selector | `CF_WORKERS_AI_MODEL_BASE_URL` | `settings.cf_workers_ai_model_base_url` | Exact allowlisted model identifier or HTTP(S) Workers AI URL |

## Derived values

| Derived value | Expression |
|---|---|
| `settings.gateway` | Always `local` |
| `settings.database_path` | `data/databox.duckdb` |
| `settings.raw_catalog_path(name)` | `data/databox.duckdb` for every source |
| `settings.raw_dataset_name(name)` | Source-specific `raw_<name>` schema |
| `settings.soda_datasource_yaml` | DuckDB datasource using `database_path` |
| `settings.sqlmesh_config()` | One local DuckDB gateway plus separate local SQLMesh state DB |

## Where it is read

- **SQLMesh** — `transforms/main/config.py` returns `settings.sqlmesh_config()`.
- **Dagster dlt assets** — source jobs use Quack over `settings.database_path`
  and write physical `raw_<source>` schemas.
- **Dagster resources** — orchestration reads the local path, dlt data directory,
  source windows, and Soda datasource.
- **Local application** — local server-side code uses `settings.database_path` and reads Cloudflare Workers AI credentials. Browser code never receives these values.
- **Data dictionary** — `scripts/generate_docs.py` uses the local gateway.

## Out-of-surface configuration

Per-source API tokens are read at request time in the source packages so dlt
and pytest environment overrides work cleanly. Build metadata and tool settings
remain in `pyproject.toml`.

## Cloudflare Workers AI

The local Python/Google ADK planner uses Cloudflare only for remote model
inference. The runtime hard-allows exactly `@cf/zai-org/glm-4.7-flash`; it has
no fallback model and does not deploy a Worker. `CF_WORKERS_AI_MODEL_BASE_URL`
accepts either that exact identifier, which derives Cloudflare's official
account-specific `/ai/v1/chat/completions` endpoint from
`CF_WORKERS_AI_ACCOUNT_ID`, or an explicit HTTP(S) Workers AI base/endpoint URL.
Every other non-HTTP value is rejected. Validate configured credentials
explicitly with `task smoke:cloudflare-ai`. Default unit tests and `task
eval:agent` use deterministic fake model clients and make no paid/live calls.

## SQLMesh state

SQLMesh state lives in `data/sqlmesh_state.duckdb`, separate from
`data/databox.duckdb`. The data connection loads the `h3` extension while the
state connection does not; separating them avoids incompatible concurrent
DuckDB connection configuration. `task db:reset` removes both local database
files and all persisted trip-plan state.
