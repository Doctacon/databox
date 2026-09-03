# Operations runbook

Finite validation commands only; `task dagster:dev` starts a long-running UI and
must be stopped with Ctrl-C.

## Rebuild local warehouse from sources

```bash
task db:reset
task full-refresh
```

`task full-refresh` validates the configured Polaris catalog and AWS S3 writer,
launches every source marked `parallel_refresh=True` concurrently as an
independent Dagster job, verifies each authoritative Iceberg table and explicit
`_dlt_load_status`, then invokes native SQLMesh only if every source succeeded.
`SOURCE_START`/`SOURCE_END` lines and Dagster run IDs attribute interleaved logs;
overlap is calculated from timestamps around each source's `dg launch`
subprocess, proving worker-process overlap while including subprocess startup
time. Raw data lives in S3-backed Iceberg tables registered by Polaris;
`data/databox.duckdb` contains the local SQLMesh schemas such as
`environmental_observations` and `analytics`.

Before refreshing, configure the Polaris client, AWS region, S3 bucket, and
temporary AWS writer credentials documented in `.env.example`, including the
session token required by the current Compose stack. `databox_lake` must already
be provisioned with `s3://<bucket>/warehouse` as its base location and the
bucket-scoped IAM role, then start `compose.iceberg.yml`.

Static pinned AVONET is deliberately excluded from routine refresh. Run its
independent `avonet_ingest` Dagster job explicitly when a validated
`raw_avonet.species_traits` replacement is required; it has no recurring
schedule. The job preserves the pinned file/hash/schema checks and publishes the
complete validated snapshot directly as a dlt-managed Polaris Iceberg table.

## Smoke verification

```bash
task verify
cd transforms/main && ../../.venv/bin/sqlmesh test
```

`task verify` uses `DATABOX_SMOKE=1` with the same concurrent Polaris Iceberg
source path, then restates SQLMesh prod through the native CLI.

## Protected live integration

The GitHub workflow `.github/workflows/polaris-iceberg-integration.yaml` is a
manual, protected diagnostic gate rather than a durable refresh. Each of the six
routine sources gets an independent job, disposable Polaris/Postgres state, and
`integration/<run>/<attempt>/<source>/warehouse` S3 prefix. It uses GitHub OIDC;
do not add static AWS credentials or automatic PR/push/schedule triggers.

Dispatch it from the GitHub Actions UI, approve the
`polaris-iceberg-integration` environment, and inspect every matrix result. The
workflow skips SQLMesh and does not delete integration objects. See the
[verified run record](https://github.com/Doctacon/databox/blob/main/.10x/evidence/2026-09-03-protected-polaris-source-matrix.md)
for the exact claims and limits.

## SQLMesh dev loop

```bash
cd transforms/main
../../.venv/bin/sqlmesh plan dev --auto-apply --no-prompts
../../.venv/bin/sqlmesh test
```

Dev schemas use the `__dev` suffix, for example
`environmental_observations__dev.fact_bird_observation`.

## CDM row-count sanity checks

```sql
SELECT COUNT(*) FROM environmental_observations.fact_bird_observation;
SELECT COUNT(*) FROM environmental_observations.fact_weather_observation;
SELECT COUNT(*) FROM environmental_observations.fact_streamflow_observation;
SELECT COUNT(*) FROM environmental_observations.fact_earthquake_event;
SELECT COUNT(*) FROM analytics.platform_health;
```

Primary key duplicate checks should return zero:

```sql
SELECT COUNT(*) - COUNT(DISTINCT bird_observation_sk)
FROM environmental_observations.fact_bird_observation;

SELECT COUNT(*) - COUNT(DISTINCT weather_observation_sk)
FROM environmental_observations.fact_weather_observation;

SELECT COUNT(*) - COUNT(DISTINCT streamflow_observation_sk)
FROM environmental_observations.fact_streamflow_observation;

SELECT COUNT(*) - COUNT(DISTINCT earthquake_event_sk)
FROM environmental_observations.fact_earthquake_event;
```

## Broken local file recovery

```bash
mv data/databox.duckdb data/databox.duckdb.broken
task full-refresh
```

If the rebuild fails, restore the backup and inspect `.logs/` plus Dagster run
history under `.dagster/`.

## Rollback SQLMesh prod

SQLMesh plan history is the rollback mechanism:

```bash
cd transforms/main
../../.venv/bin/sqlmesh state list
../../.venv/bin/sqlmesh plan prod --restore-from <previous-plan-id> --auto-apply
```

## UI launch

```bash
task dagster:dev
```

This command is intentionally long-running. Stop it with Ctrl-C after manual UI
inspection.
