Status: active
Created: 2026-09-04
Updated: 2026-09-04

# Gate Polaris startup without enforcing backup health after startup

## Context

Databox now sequences local startup as PostgreSQL liveness, Polaris realm/schema bootstrap, pgBackRest repository and WAL verification, initial full backup when absent, then Polaris availability. Backup credentials are short-lived session credentials injected by the host; no AWS CLI or host profile is mounted inside PostgreSQL.

A subsequent proposal would have added a continuously running backup monitor and blocked Databox writes whenever the last confirmed archive exceeded the five-minute RPO. The user challenged this as disproportionate for a local Compose system and asked to follow ordinary PostgreSQL backup practice.

PostgreSQL and pgBackRest normally archive WAL continuously, run physical backups on a schedule, surface archive/repository failures operationally, and prove recovery through restore drills. They do not ordinarily make each application write synchronous with remote backup health.

## Decision

Databox MUST keep the fail-closed startup gate: on `docker compose up`, PostgreSQL starts internally, Polaris bootstrap initializes the catalog, pgBackRest verifies complete temporary credentials, repository/stanza access, and WAL archival, and an initial full backup is created and verified when absent. Polaris starts only after this gate succeeds.

Databox MUST NOT add a custom continuous backup-health monitor, proxy, PostgreSQL permission switch, or per-ingestion backup-health check in this recovery slice. After startup, PostgreSQL's configured `archive_command` remains responsible for continuous WAL delivery. Scheduled pgBackRest backup/check commands and restore drills own later operational detection and evidence.

Temporary credential expiry or a later repository outage MAY cause WAL archival and scheduled backup commands to fail without automatically shutting down Polaris or blocking every catalog write. The five-minute RPO is therefore an objective while WAL archival is healthy, not a synchronous write guarantee during an undetected or unresolved archive outage. Documentation and evidence MUST state this limit plainly.

All other recovery choices remain unchanged: one Compose file; pgBackRest; host-injected short-lived dedicated backup credentials; OpenTofu; separate same-account and same-region backup buckets; 30-day catalog PITR; 45-day Iceberg recovery history; 60-minute RTO objective; and no live AWS apply before explicit plan approval.

## Alternatives considered

- **Continuous monitor plus per-write gate:** rejected as excessive custom machinery for a local Compose runtime.
- **Stop PostgreSQL or Polaris on archive failure:** rejected because backup systems normally alert and retry rather than convert a temporary backup outage into immediate application downtime.
- **Synchronous remote recovery replica:** rejected as always-on high-availability infrastructure outside current scope.
- **No startup verification:** rejected because it would allow the authoritative catalog to begin operation without any proven recovery path.

## Consequences

The runtime stays understandable and close to standard PostgreSQL practice. Startup proves that the repository, WAL path, and initial backup work at least once per Compose lifecycle. Scheduled checks and backups must remain visible and restore drills remain mandatory.

The accepted residual risk is that a backup credential or repository failure after startup can degrade the achieved RPO until detected and repaired. A future operational need for hard continuous RPO enforcement requires a separate decision backed by measured risk, not an incremental monitor added by default.

This decision supersedes `.10x/decisions/superseded/session-injected-catalog-backup-credentials.md` only where that decision required future ongoing backup failure to revoke protected operation. Its injected temporary credential and fail-closed startup choices remain active as restated here.
