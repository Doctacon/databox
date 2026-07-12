Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-improve-catalog-and-add-field-map.md
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

## Blockers

None.
