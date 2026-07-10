Status: open
Created: 2026-07-09
Updated: 2026-07-09
Parent: None
Depends-On: None

# Compact and paginate trip-plan results

## Scope

Implement the accepted planner-result compaction governed by `.10x/specs/recommendation-card-media-layout.md`:

- collapse Evidence and Provenance by default,
- retain Agent Workflow as an independently collapsed nested disclosure,
- paginate evidence at 20 rows by default with 20/50/100 options,
- provide bounded Previous/Next controls and visible range/total,
- show at most four cards per recommendation group,
- paginate each recommendation group independently in persisted rank order,
- reset pagination safely on plan/page-size changes,
- preserve media, attribution, runtime trust guards, section order, global ranks, and responsive accessibility.

## Explicit exclusions

- No backend/warehouse pagination or schema change.
- No card carousel, infinite scrolling, wrapping pager, or hidden rank renumbering.
- No Pokédex navigation, catalog, life-list, target-bird, or watch implementation in this ticket.
- No changes to recommendation generation or persisted artifacts.

## Acceptance criteria

- Initial render shows no more than four high-likelihood and four uncommon-plausible cards.
- Each group navigates independently in pages of four with disabled boundary controls and accurate range/total text.
- Evidence and Provenance is collapsed initially and remains the final section.
- Expanded evidence defaults to 20 rows and supports exactly 20, 50, and 100 rows per page.
- Evidence and group page state resets correctly when a different plan loads; evidence also returns to a valid first page when page size changes.
- Native controls are keyboard/screen-reader operable and preserve current responsive containment.
- Existing media security, attribution, section-order, API, TypeScript, rendered accessibility, and bundle tests pass.

## Evidence expectations

Record rendered tests for empty, fewer-than-page, exact-page, and multi-page groups/evidence; independent navigation; boundary behavior; plan reset; page-size reset; disclosure defaults; accessible names; responsive containment; and unchanged bundle/API security.

## Progress and notes

- 2026-07-09: User ratified collapsed Evidence and Provenance, default 20-row evidence pagination with 50/100 options, and independent four-card recommendation-group pagination to keep the page compact.

## Blockers

None. Implementation has not been authorized in this workstream.
