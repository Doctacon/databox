Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-upgrade-place-search-feedback-and-map.md
Depends-On: .10x/tickets/done/2026-07-10-implement-target-bird-planning.md

# Stabilize target-bird heading-focus test

## Scope

Repair the nondeterministic full-suite target-bird heading focus assertion by waiting for the existing route/mount focus effect.

## Acceptance criteria

- Test-only bounded `waitFor` preserves `toHaveFocus()` semantics.
- No production source/focus/timing behavior changes.
- Repeated focused and full frontend suites pass.

## Exclusions

No Target Bird UI, route, data, or behavior change.

## Evidence expectations

Record full-suite race, exact test repair, repeated gates, and review.

## Blockers

None.

## Progress and notes

- 2026-07-11: Reproduced the immediate focus assertion failure in two full parallel frontend runs while the focused Target Bird file passed, isolating a mount-effect observation race.
- 2026-07-11: Changed only the first result heading assertion to bounded `waitFor(() => expect(heading).toHaveFocus())`; production behavior is unchanged. Focused Target Bird passed 6/6 three consecutive times, then full frontend passed 253/253 plus typecheck/build/bundle audit. Evidence: `.10x/evidence/2026-07-11-target-bird-heading-focus-test-stabilization.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-target-bird-heading-focus-test-review.md`.
- 2026-07-11: Retrospective preserved lazy-route focus timing through bounded asynchronous assertion; no additional record is needed.
