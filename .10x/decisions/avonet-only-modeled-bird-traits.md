Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Use AVONET as the only new bird-trait source

## Context

The Arizona bird Pokédex needs more detail than current eBird taxonomy, observations, GBIF occurrences, and Xeno-canto recordings provide. The user requires product facts to be pulled into and modeled in the Quack-owned DuckDB rather than retrieved from narrative websites at request time.

Research considered Wikipedia/Wikidata, Encyclopedia of Life, AVONET, AVONICHE, AvianHWI, EltonTraits, USGS BBS, and permission-restricted field guides. Wikipedia and turbo-search bird profiles were explicitly rejected. Birds of the World and All About Birds cannot be systematically ingested without separate permission. EOL has variable per-object licensing. AVONICHE/AvianHWI/EltonTraits overlap with AVONET and are unnecessary for the first profile model.

AVONET article 16586228 version 7 is public on Figshare under CC BY 4.0. Its eBird-aligned species-average sheet contains 10,661 species with morphology, measurement provenance, habitat, migration, trophic, lifestyle, and range variables.

## Decision

1. AVONET v7 will be the only new bird-trait source in the first Pokédex profile implementation.
2. The source is pinned to:
   - DOI `10.6084/m9.figshare.16586228.v7`,
   - Figshare article ID `16586228`,
   - file ID `34480856`,
   - expected file size `21,524,673` bytes,
   - expected MD5 `1445afdcfb6df784010c2ca034544bc8`,
   - license `CC BY 4.0`.
3. Ingestion will read only the `AVONET2_eBird` species-average worksheet. Raw specimen measurements, BirdLife/BirdTree duplicate taxonomies, and unrelated workbook sheets will not enter the warehouse.
4. AVONET will be an independently runnable dlt source that writes through Quack into a physical `raw_avonet` schema inside `data/databox.duckdb`.
5. SQLMesh will model one trait row per AVONET eBird-aligned scientific name and join it to conformed species only through the established normalized scientific-name key.
6. No common-name match, genus-only match, parent-species collapse, hybrid-to-parent mapping, or inferred taxonomy crosswalk is allowed.
7. Current measured baseline is 600 exact matches among 624 Arizona species. The 24 unmatched current species and all 82 hybrids will retain explicit trait-unavailable status until a separately evidence-backed crosswalk or newer licensed AVONET release exists.
8. Profile prose derived from AVONET will be deterministic formatting of modeled values and documented codebook meanings. GLM MUST NOT invent missing traits or visual field marks.
9. Every displayed trait profile will retain AVONET dataset version, DOI, CC BY 4.0 attribution, source scientific name, measurement/inference provenance, and modeled freshness.

## Alternatives considered

- **Wikipedia/turbo-search narrative profiles:** rejected because the product must use governed warehouse-modeled facts.
- **EOL text/traits:** deferred because content coverage and licenses vary per object.
- **AVONET plus AVONICHE/AvianHWI/EltonTraits:** rejected for the first slice because AVONET already provides the required broad traits and additional overlap would create reconciliation work.
- **Birds of the World/All About Birds:** rejected without formal reuse permission.
- **Force-match the 24 taxonomy changes or 82 hybrids:** rejected because plausible taxonomy guesses are not evidence.

## Consequences

- A bounded XLSX parser dependency is required in the source package.
- The downloaded workbook must be size/hash/license/version validated before parsing and must not be committed or retained as an untracked project artifact.
- AVONET's eBird taxonomy is from 2021; coverage gaps must be visible and tested.
- Structured profiles can describe morphology, habitat, migration, trophic niche, lifestyle, and range, but cannot claim plumage, field marks, behavior beyond encoded lifestyle, conservation status, or Arizona seasonality without another modeled source.
