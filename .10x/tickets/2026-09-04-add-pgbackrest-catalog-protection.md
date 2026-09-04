Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: None

# Add pgBackRest catalog backup and WAL protection

## Scope

Integrate a pinned pgBackRest runtime with the existing PostgreSQL 17.6 Compose service. Configure encrypted S3 repository access through a renewable credential process, continuous WAL archive with a maximum five-minute archive opportunity, weekly full/daily differential scheduling interfaces, retention for 30-day PITR, configuration/repository checks, a secondary encrypted logical export, deterministic non-secret catalog inventory, and operator commands.

Keep graph construction and ordinary credential-free CI hermetic. Backup commands may require configured infrastructure, but importing settings, building Compose configuration, and running unit/static tests must not contact AWS or mutate local warehouse state.

## Acceptance criteria

- PostgreSQL and pgBackRest versions are explicit and compatible; local/remote pgBackRest command paths cannot silently diverge.
- WAL archive uses pgBackRest and a PostgreSQL archive timeout no greater than 300 seconds.
- Repository configuration accepts dedicated bucket/region/path inputs and a renewable credential process; no long-lived access key is required.
- Client-side encryption requires an external secret and fails closed when absent at a real backup boundary.
- Commands exist for stanza initialization/check, full backup, differential backup, repository verification/info, and encrypted logical export.
- Retention configuration preserves physical backup dependencies and WAL for the complete 30-day PITR window.
- Backup failure and stale archive state are legible to the operator.
- The catalog inventory is deterministic, excludes secrets, and records versions, schema/realm/catalog identity, table locations, metadata locations, and snapshot IDs.
- Tests cover absent/expired credential-process output, malformed credential JSON, missing encryption secret, archive configuration, retention, no-I/O construction, and secret redaction.
- Focused tests, Compose rendering, Ruff, format, MyPy, secret scan, and diff checks pass without AWS calls or live backup writes.

## Explicit exclusions

- Live backup upload or AWS apply.
- Restore/cutover implementation owned by the recovery-drill child.
- Static access keys.
- High availability.
- Provider refresh or SQLMesh behavior changes.

## References

- `.10x/decisions/polaris-iceberg-backup-and-recovery.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/research/2026-09-04-polaris-iceberg-disaster-recovery.md`
- `compose.iceberg.yml`

## Evidence expectations

Record exact rendered PostgreSQL/pgBackRest configuration, credential-process and redaction tests, backup command dry/static validation, changed files, all commands/results, and explicit no-live-AWS/no-provider limits.

## Progress and notes

- 2026-09-04: Opened from the ratified disaster-recovery architecture.
- 2026-09-04: Timeboxed implementation added an explicit PostgreSQL 17.6/pgBackRest 2.55.1 image, encrypted 30-day repository template, renewable credential-process validator, 300-second WAL archive configuration, backup/check/info Task interfaces, environment documentation, and focused hermetic tests. The ticket remains open because automatic weekly/daily scheduling, repository verification, encrypted logical export, and catalog inventory are not yet implemented; no live AWS or backup operation ran.

## Blockers

Repository automation still needs scheduling, repository verification, encrypted logical export, and deterministic catalog inventory. Live repository checks require provisioned infrastructure and belong to the live apply/proof ticket.
