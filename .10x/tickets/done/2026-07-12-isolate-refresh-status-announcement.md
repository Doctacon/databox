Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-11-upgrade-map-catalog-and-refresh-controls.md
Depends-On: .10x/tickets/done/2026-07-12-harden-refresh-lifecycle-and-recovery.md

# Isolate refresh status announcement

## Scope

Repair the final full-frontend regression caused by the header's initial refresh-status recovery announcement sharing an unnamed `role=status` with unrelated page-local operation status.

## Acceptance criteria

- The initial refresh-status recovery announcement has a specific accessible name so unrelated page-local unnamed status queries and assistive-technology context remain distinguishable.
- The dedicated refresh component test asserts that name.
- Focused refresh/My Birds tests, full frontend suite, TypeScript, production build, bundle audit, and diff check pass.
- No unrelated behavior or tests are weakened.

## Evidence expectations

Record the failing baseline, minimal diff, commands/results, and no-live-workflow limits.

## Exclusions

No backend change, refresh lifecycle change, live workflow, or unrelated test modification.

## Progress and notes

- 2026-07-12: Opened from the final aggregate rerun: 271 frontend tests passed and `app/src/MyBirds.test.tsx:192` failed because two unnamed status regions were present.
- 2026-07-12: Added the specific accessible name `Source refresh status` only to the header's initial recovery announcement and updated its dedicated component assertion; unrelated page tests were unchanged.
- 2026-07-12: Focused refresh/My Birds tests passed 23/23. Final TypeScript, full frontend (18 files/272 tests), production build, bundle audit, and diff checks passed. Evidence: `.10x/evidence/2026-07-12-refresh-status-announcement-isolation.md`.
- 2026-07-12: Acceptance mapping re-read and complete. Retrospective found the regression came from two legitimate live regions lacking distinct accessible identities; naming the new global status was narrower and more accessible than weakening the established local operation test. No broader convention or follow-up is warranted.

## Blockers

None. Final independent reviews and aggregate closure remain owned by `.10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md`.
