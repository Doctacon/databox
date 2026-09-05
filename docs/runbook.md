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

PostgreSQL first reports only basic database liveness. Polaris bootstrap then
initializes the schema and realm. The one-shot `catalog-backup-readiness` service
validates complete host-injected short-lived backup credentials, the pgBackRest
repository and stanza, a WAL archive round trip, and an existing or newly created
post-bootstrap full backup. The Polaris API remains stopped when any check fails;
inspect the backup-readiness service output rather than bypassing protection.

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

## Plan recovery infrastructure

Recovery infrastructure is declared in `infra/recovery/` with OpenTofu
`>=1.8,<2`. It creates one same-account, same-region catalog-backup bucket for
pgBackRest. The accepted same-account and `us-west-1` design does not protect
against account-wide or regional failure. Iceberg warehouse objects are not
copied: use Iceberg snapshots for logical rollback while objects remain, and
rebuild complete warehouse loss from canonical sources.

Copy `infra/recovery/terraform.tfvars.example` to an ignored `.tfvars` file and
replace every placeholder. Configure `aws_profile` in an AWS shared config file
with renewable credentials; do not put credentials in OpenTofu variables or
state. The catalog-backup role is scoped only to its dedicated bucket.

Review only—these commands do not apply infrastructure:

```bash
cd infra/recovery
tofu init -backend=false
tofu fmt -check
tofu validate
tofu plan -refresh=false -var-file=recovery.auto.tfvars -out=recovery.tfplan
```

`plan` still evaluates provider configuration and requires the configured AWS
profile. Do not run `tofu apply` until the plan is reviewed and separately
authorized. OpenTofu does not manage or mutate the primary Iceberg bucket.

## Catalog backup and recovery preparation

The PostgreSQL image includes pgBackRest and archives WAL with
`archive_timeout=300s`. On the host, obtain a short-lived session for the
dedicated catalog-backup role and set `DATABOX_BACKUP_AWS_ACCESS_KEY_ID`,
`DATABOX_BACKUP_AWS_SECRET_ACCESS_KEY`, and
`DATABOX_BACKUP_AWS_SESSION_TOKEN`. Configure the OpenTofu catalog-backup
output and `PGBACKREST_REPO1_CIPHER_PASS`; never commit or log these runtime
secrets. The PostgreSQL image does not install AWS CLI or mount host AWS
profiles. The pgBackRest repository path is intentionally fixed at `/polaris`.
Run `task catalog:backup-check` before the weekly `catalog:backup-full` or daily
`catalog:backup-diff`, and inspect `task catalog:backup-info` after each run. All
four manual commands execute pgBackRest as the container's `postgres` user.
These commands are not scheduled automatically and do not prove the recovery
objectives.

Prepare—do not execute—a restore destination with:

```bash
uv run python scripts/platform/catalog_recovery.py \
  --target /empty/recovery/postgres \
  --active /active/postgres \
  --recover-to 2026-09-04T12:00:00Z \
  --prepare-only
```

The helper rejects the active or any non-empty destination and explicitly keeps
writers and authoritative backup archiving disabled and bootstrap forbidden. A
bad table publication should use a validated Iceberg snapshot rollback while its
objects remain. Complete primary-warehouse loss requires source rebuild and is
not covered by the 60-minute catalog RTO. Last-resort table registration must use
a validated metadata location, never lexicographic S3 listing. Live PITR
execution, registry-derived restored-table validation, and the timed catalog
RPO/RTO drill remain blocked until infrastructure apply is separately approved.

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
