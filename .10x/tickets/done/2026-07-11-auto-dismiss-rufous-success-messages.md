Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-upgrade-place-search-feedback-and-map.md
Depends-On: None

# Auto-dismiss Rufous success messages

## Scope

Implement one shared 3,000-ms success-status hook/helper and migrate every user-visible Rufous success banner under `.10x/specs/transient-success-feedback.md`.

## Acceptance criteria

- Every success banner appears then disappears at 3,000 ms; replacement resets timer; unmount cleans up.
- Errors, warnings, pending, delivery-unknown, persisted status, and data remain visible/unchanged.
- Existing focus/live announcements and action concurrency remain correct.
- Static inventory prevents unmanaged success timers/surfaces.
- Fake-timer focused tests and full frontend/type/build/bundle gates pass.

## Exclusions

No toast library, animation, copy/style change, mutation behavior, or non-success timeout.

## Evidence expectations

Record success-surface inventory, timer/replacement/error/unmount matrices, accessibility and full gates/review.

## Blockers

None.

## Progress and notes

- 2026-07-11: Inventoried exactly three production success banners: My Birds page mutations/alerts, profile collection controls, and accepted Trip Calendar actions. Planner/Target results are persisted views rather than success banners. Static tests require one shared-hook invocation per production success render site.
- 2026-07-11: Added one `useTransientSuccess` hook with the exact 3,000ms constant, same-message replacement reset, explicit action clearing, and unmount cleanup. Migrated all three banners without changing copy/style, focus/live markup, mutations, invalidation, or concurrency. Calendar pending/delivery-unknown/nonaccepted states remain persistent and untimed.
- 2026-07-11: Fake-timer lifecycle/inventory and Calendar tests passed 13/13; My Birds passed 19/19. Full frontend passed 259/259 plus typecheck, build, and bundle audit. Evidence: `.10x/evidence/2026-07-11-transient-success-feedback.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-transient-success-feedback-review.md`.
- 2026-07-11: Retrospective centralized timer ownership and static inventory; no additional record is needed.
