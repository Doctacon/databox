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
replace every placeholder. Configure `aws_profile` in an AWS shared config file with renewable
credentials; do not put credentials in OpenTofu variables or state. OpenTofu
declares the console-only `databox-recovery-operator` user without an access
key, login profile, password, or MFA seed. Its inline policy permits only
assuming the bucket-scoped catalog-backup role and the two OAuth actions AWS
requires for `aws login --remote`, scoped to the account's `us-west-1` remote
public client. It cannot use same-device login or other sign-in clients. After
its separately reviewed apply, root
must manually enable console access and MFA for that user; passwords, recovery
codes, and MFA secrets must never enter OpenTofu configuration or state. The
human then uses `aws login` for the operator source profile and an AWS CLI role
profile configured with `role_arn`, `source_profile`, and `mfa_serial`. The
human enters MFA when calling `AssumeRole`; AWS returns ordinary short-lived
role credentials for host injection, and pgBackRest never receives MFA data.

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

OpenTofu state is intentionally local and operator-owned at
`infra/recovery/terraform.tfstate`; always run init, plan, apply, and import from
`infra/recovery/`. State and plan files are ignored by Git, and state must remain
mode `0600` on the FileVault-protected host. A second backup copy is not required;
the operator accepts manual state reconstruction after disk loss. Project cleanup
commands must never delete these files. If state is lost, stop all changes and
use reviewed `tofu import` commands for every existing resource, followed by a
reviewed refresh-only plan; never recreate or apply over untracked live resources.

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

Prepare—do not execute—an isolated restore with a new Docker volume name:

```bash
uv run python scripts/platform/catalog_recovery.py \
  --target-volume databox_polaris_recovery_20260905 \
  --active-volume databox_polaris_postgres \
  --recover-to 2026-09-05T12:00:00Z \
  --prepare-only
```

Preparation rejects the active volume, malformed names or timestamps, missing
backup settings, and any target volume that already exists. It creates no volume
or container. The explicit `--execute` path is implemented but requires separate
live-restore authorization; it creates the target, initializes only its ownership,
and runs the pinned pgBackRest image as `postgres` with secret values inherited
by environment-variable name. It mounts no active volume or socket, opens no
port, never removes the target on failure, and stops before PostgreSQL or Polaris
startup, validation, or cutover.

For a separately authorized complete timed drill, run the existing recovery
entrypoint from an interactive operator terminal:

```bash
task catalog:recovery-drill -- \
  --catalog databox_lake \
  --source-revision "$(git rev-parse HEAD)"
```

The command performs one AWS remote login and MFA-protected role export on the
operator TTY and refuses sessions with less than 15 minutes remaining. That
minimum prevents near-expiry cache reuse; it does not guarantee the 60-minute
RTO objective. Before creating a marker, it enumerates every locally retained
`.ready` WAL file, validates the bounded list and corresponding regular files,
and synchronously uploads every segment oldest-first with the same session. It
never renames or deletes WAL or archive-status files. Successful ordered pushes
through the subsequently switched marker segment are the continuity proof used
before restore. This catch-up does not retroactively protect changes that existed
only on the local machine before the command ran.

Temporary credentials are never written to `.env`, a handoff file, or preserved
container configuration. Recovery PostgreSQL starts inside a secret-free sleeper
container and receives backup credentials only in its first detached child process
while PITR fetches WAL. After promotion and marker validation, the container is
stopped, restarted, and PostgreSQL is launched again without backup credentials;
any earlier failure stops the credential-bearing process. Polaris follows the same
secret-free sleeper pattern, receives credentials only in a detached child process,
and is always stopped after validation or failure while its container remains
preserved. The command uses a microsecond-precise marker bracket,
synchronous marker and cleanup WAL pushes, a new ownership-labeled volume,
unexposed archive-disabled PostgreSQL, no-bootstrap Polaris, and the registry-derived
validator. Its report records the pre-catch-up pending count/oldest/newest segments
and the marker target-inclusion gap; it does not label that gap as continuous RPO.
End-to-end RTO starts before authentication, and a result over 3,600 seconds exits
nonzero. It never restarts the active stack, cuts over, or deletes recovery resources.

After separately authorized restored PostgreSQL and Polaris startup, validate
only the explicitly named no-port recovery container:

```bash
uv run python scripts/platform/catalog_recovery_validate.py \
  --polaris-container databox-polaris-recovery-validation-20260908-214022 \
  --catalog databox_lake \
  --recovery-target 2026-09-08T21:40:22Z \
  --source-revision e27990e
```

The validator resolves `--source-revision` to a commit and fails unless that
commit's canonical registry bytes exactly match the imported working-tree
registry. The example uses the reviewed corrected validation-contract revision;
record the distinct historical code revision for the selected recovery point in
the drill evidence. It derives every expected raw table and per-source
`_dlt_load_status` from `databox.config.sources.SOURCES`. It rejects a container
that lacks the recovery-validation label, is stopped, or publishes a host port.
It enumerates the restored catalog, loads every expected table with
Polaris-vended credentials, requires a current snapshot, plans its manifests,
and performs a read-only limit-one data scan. Empty tables pass when that path
completes with zero rows. Output is bounded and secret-free. Missing, malformed,
unreadable, or undeclared tables inside canonical namespaces exit nonzero.
Namespaces and tables outside the canonical registry remain prominent warnings
and do not fail recovery by themselves; they are never silently allowlisted or
deleted. The validator never contacts the active catalog, bootstraps, writes,
refreshes sources, cuts over, or cleans up recovery artifacts. Run it only after
separately authorizing the exact recovery target and container.

A bad table publication should use a validated Iceberg snapshot rollback while
its objects remain. Complete primary-warehouse loss requires source rebuild and
is not covered by the 60-minute catalog RTO. Last-resort table registration must
use a validated metadata location, never lexicographic S3 listing. Live PITR
execution and the timed catalog RPO/RTO drill remain separately authorized work.

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
