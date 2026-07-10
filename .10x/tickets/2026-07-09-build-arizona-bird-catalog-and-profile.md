Status: open
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/2026-07-09-model-avonet-traits-and-arizona-catalog.md

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

## Blockers

Depends on the modeled Arizona catalog and AVONET trait interface.
