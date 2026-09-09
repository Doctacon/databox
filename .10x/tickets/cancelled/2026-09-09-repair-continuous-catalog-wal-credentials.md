Status: cancelled
Created: 2026-09-09
Updated: 2026-09-09
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: None

# Repair continuous catalog WAL credential lifecycle

## Scope

Resolve the credential-lifecycle contradiction exposed by the timed drill: PostgreSQL's long-running `archive_command` cannot continuously archive WAL using a temporary MFA-issued role session injected only at container startup. Restore the five-minute catalog RPO contract without mounting AWS profiles, persisting temporary session credentials, silently backfilling a failed objective, or weakening backup-role isolation.

## Acceptance criteria

- The selected design explicitly defines unattended credential renewal or an explicitly ratified alternative credential posture for continuous WAL archival.
- PostgreSQL can archive across the credential lifetime boundary without service restart or hidden manual intervention if the five-minute RPO remains active.
- Existing retained `.ready` WAL is enumerated, uploaded in order, and remote continuity from the last proven segment through a fresh marker is verified without deleting local or remote recovery material.
- A fresh isolated PITR drill succeeds without using a healthy primary to conceal the pre-repair RPO failure.
- Security boundaries, failure visibility, ownership, expiry/rotation, and operational procedure are documented and reviewed.

## Exclusions

- Claiming the failed drill met RPO after a manual WAL backfill.
- Production cutover.
- Recovery-artifact deletion.
- Long-lived or brokered credentials without explicit supersession of current active decisions/specification.

## References

- `.10x/evidence/2026-09-09-timed-drill-wal-gap-recovery-failure.md`
- `.10x/decisions/startup-only-catalog-backup-gate.md`
- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/specs/polaris-catalog-continuity.md`

## Progress and notes

- 2026-09-09: Opened after a live PITR could not promote and read-only inspection found retained `.ready` WAL segments 15 through 1A while prior evidence proved remote archival only through 14. The healthy primary still retains all six segment files.

## Resolution

The user explicitly accepted local-machine loss between authenticated catch-ups and rejected long-lived backup credentials. `.10x/decisions/accept-manual-wal-catchup-for-local-catalog.md` records the replacement contract. Continuous credential renewal is therefore not required for this local deployment; `.10x/tickets/2026-09-09-upload-pending-wal-before-local-recovery.md` owns the manual catch-up implementation.

## Candidate directions

1. Adopt renewable workload identity (for example IAM Roles Anywhere or a narrowly scoped host credential service) and supersede the current no-broker boundary.
2. Adopt a dedicated bucket-scoped long-lived local backup key under a FileVault-only exception, rotation procedure, and least-privilege audit, paralleling but not reusing the warehouse key.
3. Retain human MFA refresh and explicitly abandon the continuous five-minute RPO; this does not satisfy the current disaster-recovery goal.
