Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-build-rufous-field-map-ui.md

# Stabilize Field Map heading-focus test

## Scope

Repair the nondeterministic lazy-route heading focus assertion by waiting for the existing mount effect rather than asserting immediately after `findByRole`.

## Acceptance criteria

- Test uses bounded `waitFor` around the existing focus expectation.
- Product focus behavior and implementation remain unchanged.
- Repeated focused and full frontend suites pass.

## Exclusions

No UI, timing, focus, route, or production behavior change.

## Evidence expectations

Record flaky full-suite failure, exact test-only repair, repeated gates, and review.

## Progress and notes

- 2026-07-11: Aggregate full frontend run exposed a lazy-route scheduling race: `findByRole` returned the mounted Field Map heading before its existing mount effect focused it. The failure was 1/249 and showed focus still on `body`; no product code or behavior failed.
- 2026-07-11: Changed only `app/src/FieldMap.test.tsx` to wrap the existing `toHaveFocus()` assertion in bounded Testing Library `waitFor`. Product route, lazy loading, focus effect, timing, and UI remain unchanged.
- 2026-07-11: Focused Field Map tests passed 4/4 in three consecutive runs; full frontend then passed 249/249 plus typecheck/build/bundle audit. Evidence: `.10x/evidence/2026-07-11-field-map-heading-focus-test-stabilization.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-field-map-heading-focus-test-review.md`.
- 2026-07-11: Retrospective preserved lazy-route effect timing through bounded asynchronous assertion; no additional record is needed.

## Blockers

None.
