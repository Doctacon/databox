Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/2026-07-11-expand-catalog-summary-for-discovery.md

# Build catalog sort and filters

## Scope

Implement all deterministic sorts, category/family/habitat/weight intersection filters, A–Z default, reset, paging/audio lifecycle, live count, empty/error, and responsive controls in `.10x/specs/arizona-catalog-discovery-controls.md`.

## Acceptance criteria

- A–Z/Z–A/taxonomic/most-observed/latest-sighting orders and tie/null rules are exact.
- Family/habitat options are deduplicated/alphabetized; governed weight boundaries and unavailable states are exact.
- Filters/search combine with AND; changes reset page and stop audio; reset restores contract defaults.
- Native labels, keyboard/focus/live count, 320px layout, history and existing media behavior pass.
- Full frontend/type/build/bundle/privacy gates pass.

## Exclusions

No URL-persisted controls, server-side filtering, weight sorting, migration/media filters, map, or profile layout.

## Evidence expectations

Record boundary/tie/intersection matrices, option ordering, lifecycle/accessibility/responsive and full regressions.

## Blockers

Depends on expanded strict summary API.
