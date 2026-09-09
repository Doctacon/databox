Status: active
Created: 2026-09-04
Updated: 2026-09-04

# Polaris catalog continuity

## Purpose and scope

Define backup, point-in-time restore, credential, restore-validation, and recovery-drill behavior for the PostgreSQL metastore used by the local Apache Polaris service.

This specification does not provide PostgreSQL high availability, make Polaris always-on, apply live AWS resources without a reviewed plan, replace Iceberg snapshot rollback for a bad table publication, or independently back up Iceberg warehouse objects. It requires backup health before Polaris starts; it does not synchronously enforce backup health after startup.

## Recovery objectives

- For this local deployment, off-machine catalog durability is established at explicit operator-authenticated WAL catch-up points; loss since the last successful catch-up is accepted if the local machine or disk is lost.
- Databox MUST NOT claim a continuous five-minute off-machine RPO for the local deployment.
- Catalog recovery time objective MUST be at most 60 minutes after the operator starts the authenticated catch-up-and-recovery command.
- Base backups and every WAL segment successfully archived in the preceding 30 days MUST be retained.
- The RTO MUST be described as unproven until a live timed restore drill completes successfully.

## Fail-closed availability gate

- One `compose.iceberg.yml` MUST remain the operator-visible runtime definition; separate normal and backup Compose modes MUST NOT be introduced.
- PostgreSQL MAY start internally for recovery initialization, but Polaris, bootstrap-dependent catalog service, and writers MUST remain unavailable until the backup gate succeeds.
- The gate MUST validate complete short-lived session credentials injected by the host, repository access, stanza configuration, and a WAL archive round trip.
- The gate MUST inspect machine-readable repository metadata, create a full backup when no successful full exists or the newest full is at least seven days old, create a differential backup when the newest successful backup is at least 24 hours old, and otherwise skip unnecessary backup creation. Any requested backup MUST be visible and successful before Polaris becomes available.
- Missing, partial, expired, or invalid backup settings; repository failure; WAL failure; or missing required backup state MUST fail startup clearly. No startup bypass is permitted.
- After startup, PostgreSQL's `archive_command` MUST attempt WAL delivery and later credential/repository failures MUST remain locally retained and surface through manual backup/check commands or the next startup gate. Databox MUST NOT add a custom continuous monitor, proxy, PostgreSQL permission switch, per-ingestion backup-health gate, in-container cron daemon, or host scheduler in this slice.
- Before backup or recovery reliance, one operator-authenticated command MUST enumerate all retained pending WAL, upload it oldest-first, and verify remote continuity through a fresh marker. It MUST NOT claim that catch-up retroactively protected the pre-catch-up period.
- Recovery environments MUST keep writers disabled and MUST NOT archive restored test history into the authoritative repository.

## Backup behavior

- PostgreSQL MUST use pgBackRest physical backups and WAL archiving; the local deployment MAY retain WAL locally until an explicit authenticated catch-up.
- WAL archival configuration MUST force an archive opportunity at least every five minutes while credentials remain valid, and pending WAL MUST remain locally available for the next catch-up.
- The repository MUST be a dedicated configurable AWS S3 bucket in `us-west-1`, MUST use the intentionally fixed `repo1-path=/polaris`, and MUST NOT be the primary Iceberg warehouse or Iceberg recovery bucket.
- Repository contents MUST be encrypted client-side with a secret supplied outside tracked files. S3 transport and at-rest encryption MUST remain enabled.
- Credentials MUST be short-lived credentials for the dedicated catalog-backup role, obtained by the host and injected at runtime as a backup access key, secret key, and session token. Long-lived access keys MUST NOT be required or documented as the normal path.
- The PostgreSQL image MUST NOT install AWS CLI or mount host AWS profiles, SSO caches, credential-process executables, or the complete `~/.aws` directory.
- The local stack is assumed to restart reasonably often. Its startup gate MUST apply the weekly-full/daily-differential cadence using repository timestamps; manual full, differential, check, and info commands MUST remain available for unusually long-running sessions.
- pgBackRest configuration checks and repository metadata verification MUST fail closed and surface actionable errors. Only an isolated restore drill may be represented as end-to-end recovery proof.
- Retention MUST preserve every physical backup dependency and WAL segment required for the 30-day PITR window.

## Restore validation

Databox MUST NOT maintain a separate pre-disaster catalog inventory. A completed isolated restore MUST be validated conventionally against the application and warehouse interfaces:

- start the restored PostgreSQL and compatible Polaris version with bootstrap and writers disabled;
- authenticate to the restored Polaris realm;
- enumerate restored catalogs, namespaces, and tables through the canonical Polaris/Iceberg interface;
- derive expected registry-owned tables from the Databox source registry at the Git revision corresponding to the selected recovery point, without a second hardcoded list;
- load every restored registered table through the Iceberg catalog;
- derive canonical namespaces from the same source registry; explicitly report every namespace and table outside that set as noncanonical warnings without treating their presence alone as recovery failure;
- fail on undeclared tables inside canonical namespaces, and on missing, malformed, or unreadable canonical state;
- when the primary warehouse remains available, verify each current metadata object and snapshot is readable from S3;
- when the primary warehouse is lost, report catalog-only validation limits and route reconstruction through the existing source-refresh path rather than claiming object recovery;
- run representative read-only queries when warehouse objects remain available; and
- record observed objects, failures, selected recovery point, code revision, and elapsed time as drill evidence.

The restore-validation report is temporal evidence, not a backup or independent source of authority. It MUST exclude credentials, tokens, sensitive environment values, signed URLs, and provider payloads.

## Restore behavior

- Restore MUST target a new empty isolated PostgreSQL volume by default and MUST refuse to overwrite the active catalog volume.
- Polaris and PostgreSQL MUST initially start at versions compatible with the restored backup. Upgrade occurs only after recovery validation.
- Recovery MUST support selecting a timestamp inside the retained PITR window.
- Restore automation MUST stop before production cutover and print the exact remaining operator-controlled action.
- `scripts/platform/catalog_recovery.py` MUST be the single recovery entrypoint. Its interactive `drill` command MUST be exposed through a thin Task target, require an operator TTY, perform the reviewed AWS operator-login and MFA-protected backup-role profile flow, capture temporary role credentials only through an in-memory pipe, and never print or persist credential values.
- The interactive drill command MUST fail before mutation when authentication, credential lifetime, TTY, repository, active-state, or resource-name preconditions fail; enumerate and synchronously upload every retained pending WAL segment oldest-first before selecting a microsecond-precise marker-bracketed target; verify remote continuity through that target; orchestrate new-volume restore, isolated PostgreSQL/Polaris startup, and registry-derived validation; measure end-to-end RTO from before authentication; fail the 60-minute RTO objective without discarding measured values; report the pre-catch-up durability lag separately from the marker target-inclusion gap; clean or idempotently reconcile its exact active marker; and preserve isolated recovery artifacts for separately authorized cleanup.
- Temporary backup and warehouse credentials MUST NOT be stored in preserved Docker container configuration. Recovery PostgreSQL MAY receive backup credentials only in its first child process environment while PITR fetches WAL; after promotion it MUST be restarted with archival disabled and without credentials, and any failure before that scrub restart MUST stop the credential-bearing process. Recovery Polaris MAY receive credentials only in its child process environment and MUST be stopped after validation or failure while its secret-free container remains preserved.
- Bootstrap MUST NOT replace or silently initialize restored realm state.
- Writers MUST remain disabled until restored identities, permissions, registry-owned tables, table pointers, metadata objects, snapshots, and representative Iceberg reads validate.
- Recovery credentials MUST be distinct from routine source-writer authority where AWS policy permits.

## Acceptance scenarios

### Protected startup

Given complete valid backup configuration and a reachable repository, when the local stack starts, then PostgreSQL establishes and verifies pgBackRest/WAL protection before Polaris becomes available.

### Backup unavailable

Given missing, partial, expired, or invalid backup configuration or an unavailable repository, when the stack starts, then Polaris remains unavailable and the gate reports the failing prerequisite.

### Authenticated WAL catch-up

Given a running local Polaris/PostgreSQL stack with retained pending WAL, when an operator starts backup or recovery with fresh MFA-issued credentials, then Databox uploads every pending segment oldest-first and verifies continuity through a fresh marker before relying on recovery.

### Credential expiry

Given expired or unavailable injected session credentials after startup, when WAL archival runs, then it fails visibly, retains pending WAL locally, and does not fall back to host profiles, credential brokers, or long-lived embedded credentials. Polaris is not required to shut down automatically. Loss of the local machine before the next authenticated catch-up may lose those pending catalog changes and is an accepted local-deployment risk.

### Point-in-time restore

Given a retained base backup and complete WAL sequence, when an operator selects a target timestamp, then automation restores into an empty isolated volume, starts a compatible recovery stack, and leaves the active stack untouched.

### Verification

Given a completed isolated restore and the Databox code revision corresponding to its recovery point, when the primary warehouse remains available and the recovery validator runs, then it authenticates to Polaris, derives expected registry-owned tables and canonical namespaces from that revision, enumerates and loads restored tables through the Iceberg catalog, verifies metadata/snapshot readability and representative queries, fails on missing, malformed, unreadable, or undeclared-in-canonical-namespace state, and prominently reports outside-registry namespaces and tables as noncanonical warnings. Warning state alone does not fail recovery and is never silently ignored, treated as canonical, or automatically deleted. Complete primary-warehouse loss is rebuilt from sources and is outside the 60-minute catalog-recovery objective.

### Timed drill

Given provisioned live backup infrastructure, when the first full drill runs, then evidence records the previous successful off-machine archive point, pending-WAL catch-up span, selected recovery point, marker target-inclusion gap, elapsed RTO, catalog/table validation, and all limitations. It MUST NOT represent the marker gap as continuous off-machine RPO. A result over 60 minutes fails the RTO criterion without weakening it.

## Explicit exclusions

- Live `tofu apply` in the automation-first phase.
- Automatic production cutover.
- Multi-node PostgreSQL or Polaris high availability.
- An unprotected Polaris startup mode or backup bypass.
- Continuous backup-health monitoring, per-write backup synchronization, and unattended host or container scheduling.
- Storing secrets in OpenTofu state, repository files, logs, restore-validation evidence, or other artifacts.
- Maintaining a separate pre-disaster catalog inventory.
- Requiring a secondary logical `pg_dump`; physical pgBackRest PITR is the catalog backup mechanism.
- Independent Iceberg object backup, versioning, replication, or scheduled warehouse copying.
- Treating a copied Docker volume or backup-command success as recovery proof.
