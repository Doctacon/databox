Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Arizona catalog discovery controls

## Purpose

This specification extends the strict 706-row Arizona catalog with deterministic sorting and intersection filters. Filtering remains browser-local over one network-free catalog GET.

## Summary API

Each `BirdCatalogSummary` MUST add:

- `mass_g: number | null`, exact modeled AVONET body mass;
- `habitat: string | null`, exact modeled AVONET habitat label.

Unavailable traits remain null. Hybrids MUST NOT inherit parent values. Backend and browser exact-key validators MUST reject extra, malformed, non-finite, non-positive mass or overlong habitat values. Catalog cardinality, category distribution, exact identity, and media contracts remain unchanged.

## Sort

The sort dropdown MUST contain, in this visible order:

1. Name A–Z (default)
2. Name Z–A
3. Taxonomic order
4. Most public observations
5. Latest public sighting

Display name is common name, then scientific name, then species code. Name comparison uses a deterministic English case-insensitive numeric collator, then species code. Z–A reverses display-name order and uses species code as a deterministic reverse tie-break. Taxonomic order uses ascending `taxonomic_order`, then species code. Observation sort uses descending count then name A–Z. Latest sighting uses descending valid timestamp, null last, then name A–Z.

## Filters

Filters combine with AND and search. Sentinel `All …` appears first; remaining text options are alphabetical.

- Category: All categories, Hybrids, Species.
- Family: exact current family display (`family_common_name`, then scientific); include Family unavailable when present.
- Habitat: exact modeled label; include Habitat unavailable when present.
- Weight: All weights, Tiny (<20 g), Small (20–99.9 g), Medium (100–499.9 g), Large (500–1,999.9 g), Very large (≥2,000 g), Weight unavailable.

Boundaries are lower-inclusive except Tiny; no taxon may match two buckets. Reset restores empty search, Name A–Z, and all filter sentinels. Any search/filter/sort change stops active audio and resets the centered wheel taxon to the first matching result as governed by `.10x/specs/arizona-bird-wheel-catalog.md`.

## Presentation and accessibility

Controls use native labeled selects and expose a live matching count. Empty copy names search and filters rather than category only. URL persistence is excluded from this slice. Keyboard, focus, 320px layout, paging, history, and strict response failure behavior remain intact.

## Acceptance scenarios

- A fresh catalog renders display names A–Z.
- Family/habitat options are deduplicated and alphabetized with sentinel first.
- A 20 g bird is Small; 100 g is Medium; 500 g is Large; 2,000 g is Very large.
- Null mass matches only Weight unavailable.
- Hybrid/null traits never inherit parent habitat or mass.
- Observation/date ties resolve by A–Z.
- Combined search + family + habitat + weight + category returns only rows satisfying all predicates.
