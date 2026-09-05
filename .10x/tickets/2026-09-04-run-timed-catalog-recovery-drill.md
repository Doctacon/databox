Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/2026-09-04-verify-disaster-recovery-automation.md

# Run timed isolated catalog recovery drill

## Scope

After backup infrastructure, first real backup/WAL proof, isolated restore automation, and final automation verification complete, execute the reviewed PITR drill against an empty isolated target. Validate restored Polaris and readable primary Iceberg tables conventionally, record achieved catalog RPO/RTO, and stop before production cutover.

## Acceptance criteria

- A selected recovery point is restored into a new empty isolated environment without touching the active catalog.
- Polaris identity and permissions validate without bootstrap replacing restored state.
- When the primary warehouse remains readable, registry-owned tables, metadata/snapshot pointers, and representative reads validate.
- Evidence records achieved catalog RPO and end-to-end RTO; results over five minutes or 60 minutes fail their objectives without redefining them.
- Recovery resources are cleaned through reviewed non-destructive procedures while retained backups and OpenTofu state remain preserved.

## Explicit exclusions

- Production cutover.
- Iceberg object recovery or a 60-minute full-warehouse rebuild guarantee.
- Unreviewed destructive action.

## Blockers

Blocked on its dependency and separate authorization for the live drill.
