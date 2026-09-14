Status: superseded
Created: 2026-09-04
Updated: 2026-09-04

# Iceberg object recovery

## Purpose and scope

Define recoverable protection for Iceberg table metadata and data objects stored in the authoritative AWS S3 warehouse.

This specification governs backup-copy isolation, retention, deletion behavior, recovery validation, and coordination with PostgreSQL PITR. It does not define routine Iceberg compaction, snapshot expiration, or orphan-file cleanup beyond the safety constraints those future operations must respect.

## Recovery-copy behavior

- A dedicated recovery bucket MUST be separate from the primary warehouse and Polaris catalog-backup bucket.
- The recovery bucket MUST remain in the same AWS account and `us-west-1`, as explicitly selected by the user.
- OpenTofu MUST manage bucket creation/configuration, versioning, encryption, public-access blocking, replication and IAM boundaries.
- Primary Iceberg writer credentials MUST NOT grant deletion or retention-policy mutation in the recovery bucket.
- Copy behavior MUST preserve object versions for at least 45 days.
- Routine primary deletes MUST NOT make the only recoverable copy immediately unavailable. Delete-marker and version behavior MUST be explicit and tested structurally.
- Recovery configuration MUST cover Iceberg metadata JSON, manifest lists, manifests, data files, delete files, and any other object beneath the configured warehouse prefix.
- Replication or copy failure MUST be observable and MUST NOT be represented as protected state.

## Consistency boundary

For every PostgreSQL recovery point T inside the 30-day PITR window, every Iceberg object referenced by the restored catalog at T MUST remain recoverable. The 45-day object window supplies the ratified safety margin.

Infrastructure and runbooks MUST distinguish:

- catalog recovery from PostgreSQL physical backup and WAL;
- table-level logical rollback through Iceberg snapshots;
- object restoration from retained versions or the recovery bucket;
- last-resort table re-registration when PostgreSQL recovery is unavailable.

Extra objects newer than T MAY remain for later orphan reconciliation. Recovery MUST NOT delete them during the restore procedure.

## Destructive-maintenance safety

- No snapshot-expiration or orphan-file-deletion automation may violate the 45-day recovery window.
- Orphan deletion MUST NOT use a retention interval shorter than the maximum expected write duration plus an explicit safety margin.
- Object path normalization and authority changes MUST be validated before orphan deletion because path mismatches can cause data loss.
- Backup/recovery automation MUST NOT introduce snapshot expiration, orphan deletion, or compaction as a side effect.

## Recovery behavior

- Object restoration MUST be explicit, bounded to selected keys/versions or a reviewed table scope, and non-destructive to the recovery bucket.
- Writers and Iceberg maintenance MUST remain stopped while referenced objects are restored.
- After restoration, validation MUST load the table through Polaris/PyIceberg, confirm its current metadata and snapshot, and scan representative data.
- A bad data publication SHOULD use Iceberg snapshot validation and rollback rather than whole-catalog PostgreSQL restoration.
- If PostgreSQL backups are unusable, last-resort reconstruction MUST recreate security state separately and register only validated metadata locations; it MUST NOT infer a current table pointer solely from lexicographic object listing.

## Acceptance scenarios

### Primary deletion

Given a primary warehouse object with a retained recovery copy, when the primary object or current version is deleted, then the selected version remains recoverable for 45 days and normal writer credentials cannot delete it from the recovery bucket.

### Catalog PITR consistency

Given a PostgreSQL recovery target within 30 days, when its restored table pointers are enumerated through Polaris during validation, then every referenced Iceberg object can be resolved from the primary warehouse or recovery history.

### Bad table write

Given a valid prior Iceberg snapshot and a bad current publication, when recovery is initiated, then the operator can validate and roll back the affected table without restoring unrelated Polaris catalog state.

### Missing object

Given a table whose referenced object is missing from the primary warehouse, when the bounded restore procedure runs, then it restores the selected retained object version and validates the table before writers resume.

## Residual risk

Same-account and same-region recovery copies do not survive complete AWS account compromise or a regional outage. Separate IAM boundaries reduce accidental and credential-scoped deletion risk but do not remove this accepted limitation.

## Explicit exclusions

- Live infrastructure apply during automation-first execution.
- Cross-account or cross-region replication.
- Immediate propagation of destructive primary deletions as the only recovery behavior.
- Automatic broad object restoration or production cutover.
- New Iceberg maintenance jobs.
