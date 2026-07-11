Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-evolve-product-into-rufous.md
Depends-On: .10x/tickets/done/2026-07-11-implement-trip-plan-calendar-invitations.md

# Add trip-plan calendar controls

## Scope

Add strict browser status/allowed-action validation and explicit Send/Update/Retry/Reconcile calendar controls to persisted Trip Planner results under `.10x/specs/trip-plan-calendar-invitations.md`.

## Acceptance criteria

- Completed plan shows Send; accepted shows Update; pending/busy disables duplicates; unknown/failed shows only server-allowed actions.
- Every side effect requires explicit confirmation and announces native busy/success/error status with focus coherence.
- Wording says local Bridge accepted, never inbox/calendar delivered.
- Reload/direct/history replay status without sending; create plan does not send.
- Backend message/config/recipient/raw payload cannot reach UI; strict malformed relationship tests fail closed.
- Full planner/target/My Birds/alert/frontend accessibility/type/build/bundle tests pass.

## Explicit exclusions

No backend event logic, cancellation, new recipient UI, automatic send, or theme-wide restyle.

## Evidence expectations

Record first/update/concurrent/unknown/failed/reload flows, no-implicit-send, strict client attacks, accessibility and full frontend gates.

## Blockers

Depends on trip invite API.
