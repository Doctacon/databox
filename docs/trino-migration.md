# Trino + Iceberg migration

## Current boundary

Trino 483 runs as one coordinator/worker container on `127.0.0.1:8081`.
The active deployment selects `DATABOX_SQLMESH_GATEWAY=trino` in `.env`.
All 13 models are materialized in SQLMesh's `prod` environment, and production
quality checks pass. Existing DuckDB outputs and state are retained for rollback.
The code's unset fallback remains `local`; the deployment explicitly chooses Trino.

- Trino `polaris_aws` routes raw reads to the existing Polaris `databox_lake` catalog.
- Trino `databox` routes outputs to the separate Polaris `databox_analytics` catalog.
- Analytics storage uses `s3://<warehouse bucket>/sqlmesh-warehouse`, separate from
  the raw catalog's `warehouse/` prefix. Polaris forbids overlapping catalog locations.
- Analytics alone enables `polaris.config.drop-with-purge.enabled`; SQLMesh needs
  table and view cleanup. The raw catalog's protection is unchanged.
- Trino receives the existing warehouse AWS credentials and Polaris OAuth credentials.
  No AWS CLI login or new IAM policy is required for the validated local setup.
- SQLMesh state stays local in `data/sqlmesh_trino_state.duckdb`, separate from the
  legacy gateway's `data/sqlmesh_state.duckdb`. This is a local setup, not a
  production-grade shared state service.

Model SQL remains authored in DuckDB dialect; SQLMesh/SQLGlot emits Trino SQL.
This does not mean arbitrary DuckDB extensions or SQL constructs are supported.
`analytics.platform_health.age` is replaced by the explicitly named BIGINT
`age_seconds`: Iceberg cannot represent the original interval column. Consumers
of that field must use elapsed seconds after rebuilding the model.

## Provision and start

```bash
uv sync
uv run python scripts/platform/provision_trino_catalog.py
# Use docker-compose if the docker compose plugin is unavailable.
docker compose --env-file .env -f compose.iceberg.yml up -d trino
uv run python scripts/platform/verify_trino.py
uv run python scripts/platform/verify_trino_sqlmesh.py
```

Provisioning is idempotent and refuses to overwrite a mismatched analytics
catalog. It reuses the storage role but narrows analytics allowed locations to
its own prefix. The writer must have S3 access to that prefix. It does not change
IAM policies or the raw catalog.

The first verification script exercises create, insert, update, view, select,
delete and drop. The second exercises SQLMesh plan/apply, incremental upsert and
environment views. Both use unique namespaces and clean up only their objects.

## Deployment and rollback

```bash
# Materialize/refresh production using the active .env gateway:
./scripts/analytics/sqlmesh_plan_prod.sh
# Run all production quality contracts:
uv run python -c 'from databox.orchestration.parallel_refresh import run_soda_prod; run_soda_prod()'
```

The gateway setting controls Dagster SQLMesh, the production plan wrapper,
semantic metric SQL output and Soda verification. Soda chooses `polaris_aws`
for raw contracts and `databox` for modeled contracts. Restart any long-lived
Dagster or metric-serving processes after changing the setting: settings and
SQLMesh contexts are loaded/cached in-process. None were running at cutover.

For rollback, set `DATABOX_SQLMESH_GATEWAY=local` in `.env` and restart those
processes. The retained `data/databox.duckdb` and `data/sqlmesh_state.duckdb` are
independent of Trino's state and outputs. They represent the pre-cutover output
snapshot; rebuild deliberately if freshness is required. Do not delete either
engine's state or Iceberg outputs as part of switching the gateway.

This remains a loopback-only, single-user deployment. SQLMesh's Trino adapter
skips model `grants` declarations; those declarations are not an enforced access
boundary. Multi-user access controls and shared SQLMesh state require separate
hardening before exposing this service remotely.

## Validation checkpoint (2026-09-18)

- Repository tests: `pytest tests --no-cov -q` — 652 passed. Changed Python files
  passed Ruff; `git diff --check` passed. Coverage aggregation was not run.
- Existing AWS identity verified as `databox-lake-user`; warehouse access passed.
- Trino started; direct Iceberg DML, REST views and cleanup passed in analytics.
- Isolated SQLMesh incremental upsert and environment-view lifecycle passed.
- The two source-table 404s were traced to PostgreSQL index ordering after an
  Alpine/musl-to-Bookworm/glibc image change, not missing Iceberg data. A protected
  logical backup was restored and verified before live indexes were rebuilt.
  All 97 catalog entity lookups and all 28 raw table sample reads then passed.
  See [PostgreSQL collation safety](runbook.md#postgresql-collation-safety) for
  repair evidence and the remaining collation-version tracking caveat.
- The repaired source exposed one further weather-model portability issue:
  NOAA's ISO timestamp strings need explicit parsing before conversion to DATE.
  This was fixed and regression-tested, including live DuckDB render/evaluation.
- All 13 models now materialize and are promoted into the `trino_verified`
  development environment. All 13 modeled Soda contracts passed there, as did
  the raw NOAA daily-weather contract. The raw eBird hotspots contract passed
  in the preceding validation.
- DuckDB gateway render and live evaluation of the edited earthquake model passed;
  SQLMesh's seven model tests also passed. Existing DuckDB outputs were not rebuilt.
- Latest local logs: `.logs/catalog-index-repair-raw-validation.log` (28 raw
  tables), `.logs/catalog-index-repair-trino-plan.log` (13-model environment),
  `.logs/catalog-index-repair-soda.log` (contracts),
  `.logs/catalog-index-repair-tests.log` (652 tests). Earlier incremental lifecycle
  evidence remains in `.logs/trino-incremental.log`.

## Production cutover (2026-09-18 UTC)

- Production plan/apply succeeded for all 13 models in Trino.
- All 20 committed Soda contracts passed through the production orchestration
  helper, including raw and modeled contracts.
- Production and `trino_verified` have identical row counts and rows across all
  models (the live `platform_health.age_seconds` field is excluded from row
  comparison). A semantic species-richness query executed successfully.
- `.env` now selects Trino and retains mode `0600`. Fresh-process Dagster
  definitions load, SQLMesh selects Trino without a gateway override, and the
  default engine successfully queries the production weather fact.
- All 652 repository tests pass with the active deployment configuration.
- A post-cutover pgBackRest backup completed successfully:
  `20260918-122538F_20260919-000240D`. A checkpointed, byte-verified copy of the
  Trino SQLMesh state is retained privately at
  `~/.local/state/databox/trino-cutover-20260918T235600Z/sqlmesh_trino_state.duckdb`.
  `gateway-before.json` alongside it records the previous gateway selection.
- Logs: `.logs/trino-production-cutover-plan.log`,
  `.logs/trino-production-cutover-quality.log`,
  `.logs/trino-production-cutover-parity.log`,
  `.logs/trino-production-cutover-runtime.log`, and
  `.logs/trino-production-cutover-tests.log`.

Query production at `databox.environmental_observations.<model>` and
`databox.analytics.platform_health` through `http://127.0.0.1:8081`.
The separate `__trino_verified` schemas remain available for comparison.

### Initial raw-catalog probe leftovers

Before discovering the raw catalog's view-drop restriction, the trial created:

- `trino_probe_f83f98c38682.probe` and `.probe_view`
- `sqlmesh__environmental_observations.environmental_observations__dim_weather_station__3285620844__dev`
- `environmental_observations__trino_canary.dim_weather_station` (view)

These are isolated test objects, not raw source mutations. Polaris rejects view
cleanup while purge is disabled. They were left intact rather than weakening raw
protection. Their original SQLMesh state is retained privately at
`.runtime/trino-migration/raw-catalog-canary-state.duckdb`. Removal requires a
separately considered cleanup approach; do not enable purge globally merely to
remove these probes.
