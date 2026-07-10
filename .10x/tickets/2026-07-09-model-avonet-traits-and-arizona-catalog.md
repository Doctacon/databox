Status: open
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/2026-07-09-add-avonet-bird-traits-source.md

# Model AVONET traits and Arizona bird catalog

## Scope

Implement the SQLMesh and warehouse interfaces governed by `.10x/specs/avonet-bird-traits-source.md` and `.10x/specs/arizona-bird-catalog-and-profile.md`:

- `environmental_observations.dim_bird_species_traits`,
- `birding_agent.arizona_species_catalog`,
- exact normalized-scientific-name conformance only,
- raw and human-readable AVONET codebook fields,
- measurement/inference/source provenance,
- public reviewed eBird activity aggregates,
- GBIF occurrence and Xeno recording aggregates,
- bounded deterministic public-location detail interface,
- Soda/SQLMesh contracts, tests, schema/CDM/data-dictionary updates.

## Explicit exclusions

- No API/React UI, personal collection tables, request-time lookup, inferred taxonomy crosswalk, private-location exposure, or catalog-wide media enrichment.

## Acceptance criteria

- Trait model has one row per exact matched conformed species with no duplicate normalized AVONET key.
- Catalog has exactly one row per latest eBird `US-AZ` regional taxon and current category baseline reconciles to 624 species/82 hybrids.
- Current compatibility baseline is explicitly measured: 600 exact species trait matches; 24 current species and 82 hybrids remain trait-unavailable unless inspected source facts change.
- Private/invalid/unreviewed observations never contribute exposed location detail; aggregate semantics match the active profile spec.
- GBIF/Xeno absence does not remove catalog rows.
- SQLMesh tests/prod plan, Soda contracts, generated schema/docs, source-layout, DuckDB cardinality, and focused review pass.

## Evidence expectations

Record source-to-model row counts, exact/missing match sets by category, duplicate/null/cardinality checks, privacy adversarial fixtures, codebook/provenance checks, SQLMesh plan/test output, and independent review.

## Progress and notes

- 2026-07-09: Ticket derived from ratified AVONET-only and warehouse-modeled profile contracts.

## Blockers

Depends on successful AVONET source ingestion.
