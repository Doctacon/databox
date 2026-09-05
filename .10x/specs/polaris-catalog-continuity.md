Status: active
Created: 2026-09-04
Updated: 2026-09-04

# Polaris catalog continuity

## Purpose and scope

Define backup, point-in-time restore, credential, restore-validation, and recovery-drill behavior for the PostgreSQL metastore used by the local Apache Polaris service.

This specification does not provide PostgreSQL high availability, make Polaris always-on, apply live AWS resources without a reviewed plan, replace Iceberg snapshot rollback for a bad table publication, or independently back up Iceberg warehouse objects. It requires backup health before Polaris starts; it does not synchronously enforce backup health after startup.

## Recovery objectives

- While Polaris is running, PostgreSQL catalog recovery point objective MUST be at most five minutes.
- Catalog recovery time objective MUST be at most 60 minutes.
- Base backups and WAL needed for any point in the preceding 30 days MUST be retained.
- The RTO MUST be described as unproven until a live timed restore drill completes successfully.
- When Polaris is stopped, no catalog writes are expected; the RPO clock applies to running service periods.

## Fail-closed availability gate

- One `compose.iceberg.yml` MUST remain the operator-visible runtime definition; separate normal and backup Compose modes MUST NOT be introduced.
- PostgreSQL MAY start internally for recovery initialization, but Polaris, bootstrap-dependent catalog service, and writers MUST remain unavailable until the backup gate succeeds.
- The gate MUST validate complete short-lived session credentials injected by the host, repository access, stanza configuration, and a WAL archive round trip.
- The gate MUST inspect machine-readable repository metadata, create a full backup when no successful full exists or the newest full is at least seven days old, create a differential backup when the newest successful backup is at least 24 hours old, and otherwise skip unnecessary backup creation. Any requested backup MUST be visible and successful before Polaris becomes available.
- Missing, partial, expired, or invalid backup settings; repository failure; WAL failure; or missing required backup state MUST fail startup clearly. No startup bypass is permitted.
- After startup, PostgreSQL's `archive_command` MUST continue WAL delivery and later failures MUST surface through manual backup/check commands or the next startup gate. Databox MUST NOT add a custom continuous monitor, proxy, PostgreSQL permission switch, per-ingestion backup-health gate, in-container cron daemon, or host scheduler in this slice.
- The five-minute RPO MUST be described as an objective while WAL archival is healthy, not as a synchronous guarantee during an unresolved post-start archive outage.
- Recovery environments MUST keep writers disabled and MUST NOT archive restored test history into the authoritative repository.

## Backup behavior

- PostgreSQL MUST use pgBackRest physical backups and continuous WAL archiving.
- WAL archival configuration MUST force an archive opportunity at least every five minutes while PostgreSQL is running.
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
- Bootstrap MUST NOT replace or silently initialize restored realm state.
- Writers MUST remain disabled until restored identities, permissions, registry-owned tables, table pointers, metadata objects, snapshots, and representative Iceberg reads validate.
- Recovery credentials MUST be distinct from routine source-writer authority where AWS policy permits.

## Acceptance scenarios

### Protected startup

Given complete valid backup configuration and a reachable repository, when the local stack starts, then PostgreSQL establishes and verifies pgBackRest/WAL protection before Polaris becomes available.

### Backup unavailable

Given missing, partial, expired, or invalid backup configuration or an unavailable repository, when the stack starts, then Polaris remains unavailable and the gate reports the failing prerequisite.

### Continuous archive

Given a running local Polaris/PostgreSQL stack with valid short-lived backup session credentials, when catalog writes occur, then pgBackRest archives sufficient WAL to make any recovery point no more than five minutes old.

### Credential expiry

Given expired or unavailable injected session credentials after startup, when WAL archival, a manual backup/check, or the next startup gate runs, then it fails visibly and does not fall back to host profiles, credential brokers, or long-lived embedded credentials. Polaris is not required to shut down automatically.

### Point-in-time restore

Given a retained base backup and complete WAL sequence, when an operator selects a target timestamp, then automation restores into an empty isolated volume, starts a compatible recovery stack, and leaves the active stack untouched.

### Verification

Given a completed isolated restore and the Databox code revision corresponding to its recovery point, when the primary warehouse remains available and the recovery validator runs, then it authenticates to Polaris, derives expected registry-owned tables from that revision, enumerates and loads restored tables through the Iceberg catalog, verifies metadata/snapshot readability and representative queries, and reports missing, unexpected, unreadable, or divergent state before any cutover. Complete primary-warehouse loss is rebuilt from sources and is outside the 60-minute catalog-recovery objective.

### Timed drill

Given provisioned live backup infrastructure, when the first full drill runs, then evidence records the selected recovery point, achieved RPO, elapsed RTO, catalog/table validation, and all limitations. A result over 60 minutes fails the RTO criterion without weakening it.

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
