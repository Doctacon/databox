Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Rufous catalog discovery and local Field Map

## Context

The 706-row Arizona catalog is difficult to explore with search plus category alone. Bird selectors preserve taxonomic source order rather than human alphabetical order. Profile media and trait panels inherit layouts that become hard to read. Rufous also lacks a visual statewide discovery surface despite having 1,676 current eligible public observations at 217 locations.

The product remains local-only, open-source-first, exact-taxon, and privacy-filtered. GET endpoints cannot perform provider discovery or writes, and browser traffic must not leak use to a remote tile service.

## Decision

1. The Arizona catalog defaults to common/display name A–Z and offers Z–A, taxonomic order, most public observations, and latest public sighting.
2. Catalog filters are category, family, AVONET habitat, and governed body-mass buckets: Tiny <20 g; Small 20–99.9 g; Medium 100–499.9 g; Large 500–1,999.9 g; Very large ≥2,000 g; unavailable remains explicit.
3. Unordered text dropdown choices are alphabetized by visible label. Sentinel actions remain first; numeric, ordinal, and chronological menus retain meaningful order.
4. Bird profiles stack Photo then Call, and show full-width Ecology before Physical traits.
5. Rufous adds a dedicated `/map` Field Map using open-source MapLibre GL JS, bundled local Arizona geometry, clustered persisted evidence, and a synchronized accessible encounter list. No external tile/font/style request is allowed.
6. Map evidence is exact current Arizona observation evidence with `is_valid=true`, `is_reviewed=true`, and `is_location_private=false`. Default is All snapshot. Optional 48-hour, 7-day, and 30-day filters use the computer's current clock, as explicitly selected by the user.
7. The first map slice includes species and family filters, clusters, exact public encounter details, profile links, freshness/empty disclosure, and access warnings. It excludes personal data and inferred range claims.

## Alternatives considered

- Bird-profile-only map: simpler but poor for statewide discovery.
- My Birds map: useful later, but mixes private collection semantics into the first public-evidence map.
- Trip Planner map: useful later, but narrows mapping to generated plans.
- Remote OpenStreetMap tiles: rejected because browser requests leak usage and violate the local runtime boundary.
- deck.gl/MVT/PMTiles first: rejected as unnecessary for the current 1,676-row evidence volume.
- Current taxonomic order as catalog default: rejected by the user as impractical for human selection.

## Consequences

Two strict summary fields—habitat and body mass—must be added to the catalog API. The map requires a bounded local Census-derived geometry artifact and a new open-source browser dependency. Map canvas behavior must always have a semantic list equivalent. Current-clock windows may become empty as a snapshot ages; freshness and All snapshot remain visible.
