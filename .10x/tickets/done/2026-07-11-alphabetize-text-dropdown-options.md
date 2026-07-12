Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-remove-wishlist-and-consolidate-watches.md

# Alphabetize text dropdown options

## Scope

Audit current selects and implement `.10x/specs/alphabetical-text-dropdown-ordering.md`, especially observation and Watch bird selectors. Use one small deterministic display-label comparator rather than duplicated ordering logic.

## Acceptance criteria

- All unordered bird/text option sets are A–Z with deterministic ties and sentinel first.
- Numeric, ordinal, chronological, navigation, and tab ordering remain unchanged.
- Stale/fallback identity and empty sets are safe; selection/mutation semantics do not change.
- Tests enumerate every current select and prove intended ordering classification.
- Full frontend/type/build/bundle and collection regressions pass.

## Exclusions

No combobox replacement, searchable custom select, catalog filter implementation, map UI, or workflow reorder.

## Evidence expectations

Record select inventory, before/after ordering, preserved exceptions, and full gates.

## Progress and notes

- 2026-07-11: Audited and test-inventoried all 12 current native selects across App, TargetBird, MyBirds, and BirdPages. Classified observation/watch/category/family/habitat as alphabetical text and preserved sort actions, numeric durations/page sizes/weight buckets, ordinal skill, and chronological saved plans.
- 2026-07-11: Added the single shared deterministic English case-insensitive numeric visible-label comparator with explicit tie labels. Catalog name/family/habitat sorting and My Birds observation/watch options now use it.
- 2026-07-11: Observation options now receive an alphabetized catalog copy; available Watch options preserve exclusions while sorting alphabetically. Input arrays are not mutated. Existing fallback common/scientific/species-code labels, stale-watch exclusion, selected value submission, empty sets, and collection mutations remain safe.
- 2026-07-11: Focused ordering/collection/catalog tests pass 45/45; full frontend passes 228/228 plus typecheck, build, and bundle audit; collection API passes 17/17 network-blocked; Ruff and secret gates pass. Evidence: `.10x/evidence/2026-07-11-alphabetical-text-dropdown-ordering.md`.
- 2026-07-11: The first targeted Python collection run passed all 17 tests but exited nonzero because repository-wide coverage was only 32.70% for the targeted subset; rerunning the same target with `--no-cov` passed 17/17. This was a test invocation issue, not a product failure.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-alphabetical-text-dropdown-ordering-review.md`.
- 2026-07-11: Retrospective preserved the select inventory and semantic-order exceptions in tests; no additional record is needed.

## Blockers

None.
