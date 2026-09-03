# Configuration

Databox has one authoritative runtime-config surface:
[`packages/databox/databox/config/settings.py`](https://github.com/Doctacon/databox/blob/main/packages/databox/databox/config/settings.py).
The `DataboxSettings` Pydantic object owns every runtime knob. Other runtime
code imports it rather than redeclaring values.

## Primary surface

| Setting | Env var | Source | Notes |
|---|---|---|---|
| Polaris URL | `DATABOX_POLARIS_URL` | `settings.polaris_url` | Local REST catalog; default `http://127.0.0.1:8181` |
| Polaris client ID | `DATABOX_POLARIS_CLIENT_ID` | `settings.polaris_client_id` | Secret; local catalog principal |
| Polaris client secret | `DATABOX_POLARIS_CLIENT_SECRET` | `settings.polaris_client_secret` | Secret |
| Iceberg catalog | `DATABOX_ICEBERG_CATALOG` | `settings.iceberg_catalog` | Default `databox_lake` |
| Warehouse prefix | `DATABOX_ICEBERG_WAREHOUSE_PREFIX` | `settings.iceberg_warehouse_prefix` | Default `warehouse`; protected integration uses run/source-isolated prefixes |
| S3 bucket | `DATABOX_AWS_S3_BUCKET` | `settings.aws_s3_bucket` | Iceberg warehouse bucket |
| AWS writer key | `DATABOX_AWS_ACCESS_KEY_ID` | `settings.aws_access_key_id` | Secret; scoped S3 writer |
| AWS writer secret | `DATABOX_AWS_SECRET_ACCESS_KEY` | `settings.aws_secret_access_key` | Secret |
| AWS session token | `DATABOX_AWS_SESSION_TOKEN` | `settings.aws_session_token` | Required by the current Compose stack and with temporary OIDC/STS credentials; the direct dlt destination accepts long-lived keys without it |
| AWS region | `DATABOX_AWS_REGION` | `settings.aws_region` | Default `us-west-1` |
| Log level | `LOG_LEVEL` | `settings.log_level` | Default `INFO` |
| Smoke mode | `DATABOX_SMOKE` | `settings.smoke` | Limits source rows for verification |
| eBird window | `DATABOX_EBIRD_DAYS_BACK` | `settings.ebird_days_back` | Default 30; provider range 1–30 |
| GBIF record cap | `DATABOX_GBIF_MAX_RECORDS` | `settings.gbif_max_records` | Default 1,000; allowed range 1–10,000 |
| GBIF release slice | `DATABOX_GBIF_PUBLIC_RELEASE` | `settings.gbif_public_release` | Default false; retained producer input behavior |
| NOAA window | `DATABOX_NOAA_DAYS_BACK` | `settings.noaa_days_back` | Default 30 |
| USGS window | `DATABOX_USGS_DAYS_BACK` | `settings.usgs_days_back` | Default 30 |
| OpenLineage URL | `OPENLINEAGE_URL` | `settings.openlineage_url` | Optional; disabled when unset |
| OpenLineage namespace | `OPENLINEAGE_NAMESPACE` | `settings.openlineage_namespace` | Default `databox` |
| OpenLineage API key | `OPENLINEAGE_API_KEY` | `settings.openlineage_api_key` | Optional secret |

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
- **Data dictionary** — `scripts/platform/generate_docs.py` uses the local gateway.

## Out-of-surface configuration

Per-source API tokens are read at request time in the source packages so dlt
and pytest environment overrides work cleanly. `DATABOX_ENV_FILE` can select a
different dotenv path; tests use it to prove credential-empty graph
construction. Build metadata and tool settings remain in `pyproject.toml`.

## SQLMesh state

SQLMesh state lives in `data/sqlmesh_state.duckdb`, separate from
`data/databox.duckdb`. The data connection loads the `h3` extension while the
state connection does not; separating them avoids incompatible concurrent
DuckDB connection configuration. `task db:reset` removes both local database
files.
