Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-fix-bird-profile-information-layout.md

# Repair stale profile-layout contract test

## Scope

Update the stale Python static assertion that requires a removed 820px media-grid override. Validate the active base `minmax(0, 1fr)` one-column profile/media contract and preserve 320px layout protections.

## Acceptance criteria

- Static test reflects active profile-layout CSS without weakening one-column/Photo-before-Call/Ecology-before-Physical guarantees.
- Focused and full Python/frontend gates pass.

## Exclusions

No CSS, markup, layout, or product behavior change.

## Evidence expectations

Record stale failure, exact test-only repair, full gates, and review.

## Progress and notes

- 2026-07-11: Reproduced the sole full-suite failure: the Python static test still required a removed 820px media-grid override despite the done profile-layout ticket moving the one-column contract to the all-width base declaration.
- 2026-07-11: Updated only `tests/test_bird_catalog_api.py` to require both profile/media base `minmax(0, 1fr)` declarations, reject the former positive `minmax(240px` media track, and retain existing 1100/820/540px and 320px-oriented protections. No CSS, markup, or behavior changed.
- 2026-07-11: Focused repair plus map tests pass 23/23; full network-blocked Python passes 701/701 at 86.63% coverage; frontend passes 245/245 plus typecheck/build/bundle; repository static and strict docs gates pass. Evidence: `.10x/evidence/2026-07-11-profile-layout-contract-test-repair.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-profile-layout-contract-test-repair-review.md`.
- 2026-07-11: Retrospective preserved the active base-grid contract in static and frontend tests; no additional record is needed.

## Blockers

None.
