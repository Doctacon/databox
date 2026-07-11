Status: done
Created: 2026-07-09
Updated: 2026-07-10
Parent: .10x/tickets/done/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-09-model-avonet-traits-and-arizona-catalog.md

# Build Arizona bird catalog and modeled profile

## Scope

Implement the read-only API and React pages governed by `.10x/specs/arizona-bird-catalog-and-profile.md`:

- native Trip Planner / Arizona Birds navigation and direct/back-forward routes,
- typed network-free `GET /api/birds` and `GET /api/birds/{species_code}`,
- searchable/filterable 706-taxon list with 24-row client pages,
- selectable accessible species/hybrid cards,
- modeled taxonomy, AVONET physical/ecology, recent public Arizona activity, GBIF/Xeno context, and provenance sections,
- explicit missing-trait/evidence states,
- deterministic source-backed wording only,
- privacy/media/credential/bundle guards.

## Explicit exclusions

- No personal observation/life-list/wishlist/watch mutation, target planning, maps, external narrative retrieval, request-time fact discovery, or catalog-wide media backfill.

## Acceptance criteria

- Direct `/birds` and `/birds/{species_code}` navigation, browser back/forward, local fallback serving, and Trip Planner preservation pass.
- List includes all 706 modeled taxa in stable taxonomic order with species/hybrid filters, search, bounded 24-row paging, and reset behavior.
- Exact-match, taxonomy-drift, hybrid, sparse, missing-source, database-busy, invalid-ID, and private-location scenarios render safely.
- Profile fields and deterministic sentences map exactly to modeled facts and preserve AVONET DOI/version/license/inference provenance.
- No GET triggers source/model/media/turbo lookup or mutation.
- Existing planner behavior, media trust, TypeScript, API, accessibility, responsive, bundle/secret, CI, and independent review pass.

## Evidence expectations

Record API contracts/cardinality/privacy, rendered navigation/list/detail/filter/pagination/empty/error cases, exact model-to-text assertions, no-network/no-write GET checks, bundle/secret scans, full regression gates, and independent review.

## Progress and notes

- 2026-07-09: Ticket derived from the active warehouse-only catalog/profile contract.
- 2026-07-10: Implemented typed read-only bird list/detail APIs, native direct/history routes, 24-card catalog paging/search/category filters, and complete modeled profile sections while preserving the Trip Planner.
- 2026-07-10: Privacy review confirmed eBird `is_location_private` is authoritative. Public modeled names containing `(private)` remain visible with an explicit site-access warning; strict API/browser shapes prevent private/raw/internal fields from reaching the browser.
- 2026-07-10: Focused API/planner tests passed 21/21; complete browser gate passed 64/64 plus typecheck/build/bundle audit. Live read-only probe reconciled 706/624/82/600 with no socket calls and an unchanged warehouse hash. Evidence: `.10x/evidence/2026-07-10-arizona-bird-catalog-and-profile.md`.
- 2026-07-10: Full repository CI reached 300 passes and 85.84% coverage; its sole failure is the pre-existing order-dependent AVONET schema artifact defect owned by `.10x/tickets/done/2026-07-10-repair-source-vcr-and-schema-snapshot-suite.md`.
- 2026-07-10: User superseded the catalog spec's global-range requirement because range metrics are outside the governed AVONET source fields; the UI retains an explicit unavailable disclosure.
- 2026-07-10: Independent-review repairs now require exactly 706 unique catalog codes and the exact 624-species/82-hybrid distribution in API and browser, strictly suppress malformed/unexpected error payloads, distinguish true/false/unknown inference, expose deterministic eBird/AVONET/GBIF/Xeno statuses, set useful native route titles, focus each newly rendered page heading once (including async profiles), and mechanically verify responsive CSS. Focused API/planner tests pass 27/27 and browser tests pass 72/72; typecheck, build, bundle audit, Ruff, MyPy, focused pre-commit, and diff checks pass.
- 2026-07-10: Final independent review passed every acceptance area. Review: `.10x/reviews/2026-07-10-arizona-bird-catalog-and-profile-review.md`.
- 2026-07-10: The separately owned source-suite isolation defect was repaired and independently reviewed; the complete network-disabled Python suite now passes 307/307 without cassette changes.
- 2026-07-10: Retrospective found no additional skill or knowledge record was needed: model-bound field limits, exact snapshot/category guards, tri-state inference, strict browser validation, privacy semantics, and route-focus behavior are preserved directly in the active specification and adversarial tests.

## Blockers

None.
