Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-upgrade-map-catalog-and-refresh-controls.md
Depends-On: None

# Build local refresh runtime and API

## Scope

Add a durable safe status/lock/launcher around the existing routine full-refresh orchestration and typed same-origin status/confirmed-launch API. The implementation owns process recovery/status but reuses ingestion logic unchanged.

## Acceptance criteria

- Exact routine source scope, one Quack lifecycle, source failure gating, SQLMesh ordering, and temporary-busy contract satisfy `.10x/specs/local-source-refresh-control.md`.
- At most one process runs; status survives reload/restart; stale/crashed process status resolves safely.
- GET/startup cannot launch; confirmation, Host/Origin, JSON shape, command/path/env immutability, redaction, and conflict checks pass.
- Success/failure simulations prove source attribution, SQLMesh suppression/run ordering, cleanup, and no automatic retry.
- Personal/runtime tables/checksums remain unchanged in isolated success/failure fixtures.

## Evidence expectations

Unit/integration tests with fake subprocess/orchestrator only; status-file atomicity/recovery tests; security/privacy review; full Python/static checks. No live provider refresh in verification.

## Exclusions

No UI, AVONET/media/model/email, arbitrary source/job selection, cancellation, scheduler, staged warehouse, state merge, live source calls, or duplicated orchestration.

## Blockers

None.

## Progress and notes

- 2026-07-11: User accepted temporary database-busy behavior rather than snapshot/staged-refresh complexity.
