Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-upgrade-place-search-feedback-and-map.md
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
