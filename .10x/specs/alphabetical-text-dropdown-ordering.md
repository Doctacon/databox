Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Alphabetical text dropdown ordering

## Purpose

Unordered human text choices MUST be easy to scan. This applies across Rufous, not only the catalog.

## Behavior

- Bird selectors MUST sort by visible display name A–Z using deterministic English case-insensitive numeric comparison, then species code.
- Family, habitat, migration, category, map species, map family, and similar unordered text choices MUST be alphabetical by visible label.
- Placeholder/sentinel choices such as `Select…`, `All …`, `Not specified`, and loading states remain first.
- Duplicate visible options MUST be removed by exact governed value before rendering.
- Empty/stale labels use existing safe fallback identity and sort by that visible fallback.

The following preserve semantic order and MUST NOT be alphabetized:

- durations, distances, radii, page sizes, weight buckets, and other numeric progressions;
- skill levels and lifecycle/status choices with an ordinal workflow;
- saved-plan history and other explicitly chronological lists;
- navigation and tab order.

## Current required surfaces

Observation bird selector, new-Watch bird selector, catalog filters/sort, and Field Map species/family selectors. Any future unordered text select inherits this contract.

## Acceptance scenarios

- The first observation bird is alphabetically first, not taxonomically first.
- `All families` precedes alphabetized family names.
- 30/60/90/120/180-minute duration remains numeric.
- Beginner/Intermediate/Advanced remains ordinal.
- Saved plans remain newest-first.
