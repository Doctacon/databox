Status: active
Created: 2026-09-04
Updated: 2026-09-04

# Polaris catalog continuity

## Purpose and scope

Define backup, point-in-time restore, inventory, credential, and recovery-drill behavior for the PostgreSQL metastore used by the local Apache Polaris service.

This specification does not provide PostgreSQL high availability, make Polaris always-on, apply live AWS resources without a reviewed plan, or replace Iceberg snapshot rollback for a bad table publication. It requires backup health whenever Polaris is available; there is no unprotected normal mode.

## Recovery objectives

- While Polaris is running, PostgreSQL catalog recovery point objective MUST be at most five minutes.
- Catalog recovery time objective MUST be at most 60 minutes.
- Base backups and WAL needed for any point in the preceding 30 days MUST be retained.
- The RTO MUST be described as unproven until a live timed restore drill completes successfully.
- When Polaris is stopped, no catalog writes are expected; the RPO clock applies to running service periods.

## Fail-closed availability gate

- One `compose.iceberg.yml` MUST remain the operator-visible runtime definition; separate normal and backup Compose modes MUST NOT be introduced.
- PostgreSQL MAY start internally for recovery initialization, but Polaris, bootstrap-dependent catalog service, and writers MUST remain unavailable until the backup gate succeeds.
- The gate MUST validate renewable credentials, repository access, stanza configuration, and a WAL archive round trip.
- A newly initialized catalog with no valid base backup MUST create and verify its initial backup before Polaris becomes available.
- Missing, partial, expired, or invalid backup settings; repository failure; WAL failure; or missing required backup state MUST fail clearly. No bypass or silent unprotected mode is permitted.
- Recovery environments MUST keep writers disabled and MUST NOT archive restored test history into the authoritative repository.

## Backup behavior

- PostgreSQL MUST use pgBackRest physical backups and continuous WAL archiving.
- WAL archival configuration MUST force an archive opportunity at least every five minutes while PostgreSQL is running.
- The repository MUST be a dedicated configurable AWS S3 bucket in `us-west-1` and MUST NOT be the primary Iceberg warehouse or Iceberg recovery bucket.
- Repository contents MUST be encrypted client-side with a secret supplied outside tracked files. S3 transport and at-rest encryption MUST remain enabled.
- Credentials MUST be renewable short-lived credentials obtained through a configured credential process. Long-lived access keys MUST NOT be required or documented as the normal path.
- Backup scheduling MUST be explicit and observable. The intended policy is weekly full backups, daily differential backups, and continuous WAL archive.
- pgBackRest configuration checks and repository verification MUST fail closed and surface actionable errors.
- A periodic logical PostgreSQL export MUST be available as a secondary inspection/version-migration artifact and MUST be encrypted before durable storage. It MUST NOT be represented as PITR-capable.
- Retention MUST preserve every physical backup dependency and WAL segment required for the 30-day PITR window.

## Inventory

A deterministic, non-secret catalog recovery inventory MUST include:

- generation timestamp;
- Polaris image/version and PostgreSQL major version;
- Polaris schema version and realm/catalog names;
- namespaces and table identifiers;
- table locations, current metadata JSON locations, and current snapshot IDs;
- the associated pgBackRest backup identifier or recovery range when available.

The inventory is diagnostic metadata, not an independent source of catalog authority. It MUST exclude credentials, tokens, sensitive environment values, and provider payloads.

## Restore behavior

- Restore MUST target a new empty isolated PostgreSQL volume by default and MUST refuse to overwrite the active catalog volume.
- Polaris and PostgreSQL MUST initially start at versions compatible with the restored backup. Upgrade occurs only after recovery validation.
- Recovery MUST support selecting a timestamp inside the retained PITR window.
- Restore automation MUST stop before production cutover and print the exact remaining operator-controlled action.
- Bootstrap MUST NOT replace or silently initialize restored realm state.
- Writers MUST remain disabled until catalog inventory, permissions, table pointers, and representative Iceberg reads validate.
- Recovery credentials MUST be distinct from routine source-writer authority where AWS policy permits.

## Acceptance scenarios

### Protected startup

Given complete valid backup configuration and a reachable repository, when the local stack starts, then PostgreSQL establishes and verifies pgBackRest/WAL protection before Polaris becomes available.

### Backup unavailable

Given missing, partial, expired, or invalid backup configuration or an unavailable repository, when the stack starts, then Polaris remains unavailable and the gate reports the failing prerequisite.

### Continuous archive

Given a running local Polaris/PostgreSQL stack with valid renewable backup credentials, when catalog writes occur, then pgBackRest archives sufficient WAL to make any recovery point no more than five minutes old.

### Credential expiry

Given expired or unavailable renewable credentials, when WAL archival or backup runs, then it fails visibly and does not fall back to long-lived embedded credentials.

### Point-in-time restore

Given a retained base backup and complete WAL sequence, when an operator selects a target timestamp, then automation restores into an empty isolated volume, starts a compatible recovery stack, and leaves the active stack untouched.

### Verification

Given a completed isolated restore, when the recovery validator runs, then it authenticates to Polaris, compares the non-secret inventory, loads every registered table through the Iceberg catalog, and reports missing or divergent pointers before any cutover.

### Timed drill

Given provisioned live backup infrastructure, when the first full drill runs, then evidence records the selected recovery point, achieved RPO, elapsed RTO, catalog/table validation, and all limitations. A result over 60 minutes fails the RTO criterion without weakening it.

## Explicit exclusions

- Live `tofu apply` in the automation-first phase.
- Automatic production cutover.
- Multi-node PostgreSQL or Polaris high availability.
- An unprotected normal Polaris startup mode or backup bypass.
- Storing secrets in OpenTofu state, repository files, logs, inventories, or evidence.
- Treating `pg_dump`, a copied Docker volume, or backup-command success as recovery proof.
