Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: None
Depends-On: .10x/tickets/done/2026-07-11-evolve-product-into-rufous.md

# Improve catalog discovery and add Rufous Field Map

## Aggregate outcome

Make the 706-row catalog easy to sort/filter/select, repair bird-profile information hierarchy, and add a dedicated local-only statewide public-evidence Field Map.

This is a parent plan and is not executable directly.

## Governing records

- `.10x/decisions/rufous-catalog-discovery-and-field-map.md`
- `.10x/specs/arizona-catalog-discovery-controls.md`
- `.10x/specs/alphabetical-text-dropdown-ordering.md`
- `.10x/specs/bird-profile-information-layout.md`
- `.10x/specs/rufous-field-map.md`
- `.10x/research/2026-07-11-rufous-catalog-and-field-map.md`
- Existing catalog, media, privacy, local-platform, accessibility, and exact-taxon contracts remain active.

## Child sequence

1. `.10x/tickets/done/2026-07-11-expand-catalog-summary-for-discovery.md`
2. `.10x/tickets/2026-07-11-build-catalog-sort-and-filters.md`
3. `.10x/tickets/2026-07-11-fix-bird-profile-information-layout.md`
4. `.10x/tickets/2026-07-11-alphabetize-text-dropdown-options.md`
5. `.10x/tickets/2026-07-11-build-field-map-data-api.md`
6. `.10x/tickets/2026-07-11-build-rufous-field-map-ui.md`
7. `.10x/tickets/2026-07-11-verify-catalog-and-field-map.md`

API summary and map-data children may execute independently. Profile layout and dropdown ordering are independent UI slices. Catalog controls depend on summary fields. Map UI depends on map data/API and local geometry. Theme-wide aggregate verification follows all children.

## Aggregate acceptance

- Catalog defaults A–Z and approved sort/filter intersections are deterministic.
- Unordered text selectors are alphabetized while numeric/ordinal/chronological menus retain semantic order.
- Profile Photo/Call stack and Ecology precedes Physical traits full width.
- `/map` provides local MapLibre clusters plus accessible list with zero third-party request and strict public-evidence eligibility.
- Full product/privacy/data/docs/static gates and independent reviews pass without unintended warehouse or delivery mutation.

## Blockers

None; execute bounded children in dependency order after implementation authorization.
