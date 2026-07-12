Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-expand-catalog-summary-for-discovery.md

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

## Progress and notes

- 2026-07-11: Implemented browser-local Name A–Z default, Name Z–A, taxonomic, most-observed, and latest-sighting sorts using a deterministic English case-insensitive numeric collator, species-code total tie-breaks, chronological timestamps, and null-last latest behavior.
- 2026-07-11: Added AND-composed category, family, habitat, and exact Tiny/Small/Medium/Large/Very large/unavailable weight filters; visible family/habitat options are deduplicated and alphabetized with unavailable options in alphabetical position after the sentinel. Reset restores all defaults.
- 2026-07-11: Search/sort/filter changes reset page 1 and stop active catalog audio. Native labeled controls, live matching count, filter-aware empty copy, responsive auto-fit/320px controls, existing navigation/media/paging semantics, and full regressions pass.
- 2026-07-11: Focused catalog browser tests pass 24/24; full frontend passes 223/223 plus typecheck/build/bundle audit; full network-blocked Python/privacy passes 679/679 at 86.59% coverage; repository lint, format, MyPy, secret, and source-layout gates pass. Evidence: `.10x/evidence/2026-07-11-catalog-sort-and-filters.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-catalog-sort-and-filters-review.md`.
- 2026-07-11: Retrospective found no additional reusable lesson beyond the deterministic comparator and boundary matrices now protected by tests.

## Blockers

None.
