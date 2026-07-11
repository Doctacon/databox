Status: done
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

## Progress and notes

- 2026-07-11: Implemented strict calendar status/action and action-response runtime validation, fixed safe API errors, and explicit confirmed Send/Update/Retry/Reconcile controls on persisted planner results. Native buttons, `aria-busy`, live status, focused outcomes, and a synchronous duplicate guard cover accessibility and concurrent clicks. Local-Bridge wording explicitly disclaims inbox/calendar delivery; persisted reload/history/create rendering causes no send.
- 2026-07-11: Added focused first/update/concurrent/unknown/failed/reload/malformed/no-implicit-send/privacy tests. Focused tests pass 46/46; all frontend suites pass 220/220; typecheck and production build/bundle privacy scan pass. Evidence: `.10x/evidence/2026-07-11-trip-plan-calendar-controls.md`.
- 2026-07-11: Independent review passed strict trust-boundary, allowed-action, confirmation, duplicate, accessibility, safe-copy, replay/no-send, and privacy criteria. Review: `.10x/reviews/2026-07-11-trip-plan-calendar-controls-review.md`.
- 2026-07-11: Retrospective found no new reusable lesson beyond the active strict browser-boundary contracts and regression tests.

## Blockers

None.
