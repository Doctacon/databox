# Configuration

Databox has one authoritative runtime-config surface:
[`packages/databox/databox/config/settings.py`](https://github.com/Doctacon/databox/blob/main/packages/databox/databox/config/settings.py).
The `DataboxSettings` Pydantic object owns every runtime knob. Other runtime
code imports it rather than redeclaring values.

## Authoritative surface

| Setting | Env var | Source | Notes |
|---|---|---|---|
| Polaris URL | `DATABOX_POLARIS_URL` | `settings.polaris_url` | Local REST catalog; default `http://127.0.0.1:8181` |
| Polaris client ID | `DATABOX_POLARIS_CLIENT_ID` | `settings.polaris_client_id` | Secret; local catalog principal |
| Polaris client secret | `DATABOX_POLARIS_CLIENT_SECRET` | `settings.polaris_client_secret` | Secret |
| S3 bucket | `DATABOX_AWS_S3_BUCKET` | `settings.aws_s3_bucket` | Iceberg warehouse bucket |
| AWS writer key | `DATABOX_AWS_ACCESS_KEY_ID` | `settings.aws_access_key_id` | Secret; scoped S3 writer |
| AWS writer secret | `DATABOX_AWS_SECRET_ACCESS_KEY` | `settings.aws_secret_access_key` | Secret |
| AWS region | `DATABOX_AWS_REGION` | `settings.aws_region` | Default `us-west-1` |
| Log level | `LOG_LEVEL` | `settings.log_level` | Default `INFO` |
| Smoke mode | `DATABOX_SMOKE` | `settings.smoke` | Limits source rows for verification |
| eBird window | `DATABOX_EBIRD_DAYS_BACK` | `settings.ebird_days_back` | Default 30; provider range 1–30 |
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
| `settings.pyiceberg_catalog()` | Authenticated Polaris REST catalog |
| `settings.raw_dataset_name(name)` | Source-specific `raw_<name>` Iceberg namespace |
| `settings.soda_datasource_yaml` | DuckDB datasource using `database_path` |
| `settings.sqlmesh_config()` | One local DuckDB gateway plus separate local SQLMesh state DB |

## Where it is read

- **SQLMesh** — `transforms/main/config.py` returns `settings.sqlmesh_config()`.
- **Dagster dlt assets** — source jobs write dlt-managed Iceberg tables in S3
  and commit their catalog metadata through Polaris.
- **Dagster resources** — orchestration reads Polaris/S3 configuration, the local
  modeled-data path, dlt data directory, source windows, and Soda datasource.
- **Local application** — local server-side code uses `settings.database_path` and reads Cloudflare Workers AI credentials. Browser code never receives these values.
- **Data dictionary** — `scripts/platform/generate_docs.py` uses the local gateway.

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
`CF_WORKERS_AI_ACCOUNT_ID`, or an explicit HTTPS `api.cloudflare.com` Workers AI
base/endpoint URL. Every other host, plain HTTP URL, and non-URL value is
rejected. Requests use Cloudflare's OpenAI-compatible strict JSON Schema
response format and retain local Pydantic plus exact-grounding validation.
Validate configured credentials and the distinct trip-plan, target-bird, and
watched-report schemas explicitly with `task smoke:cloudflare-ai`. This opt-in
check makes three bounded live requests and prints no credential values.
Default unit tests and `task eval:agent` use deterministic fake model clients
and make no paid/live calls.

## SQLMesh state

SQLMesh state lives in `data/sqlmesh_state.duckdb`, separate from
`data/databox.duckdb`. The data connection loads the `h3` extension while the
state connection does not; separating them avoids incompatible concurrent
DuckDB connection configuration. `task db:reset` removes both local database
files and all persisted trip-plan state.
