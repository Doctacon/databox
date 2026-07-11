Status: done
Created: 2026-07-09
Updated: 2026-07-10
Parent: .10x/tickets/done/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-09-add-avonet-bird-traits-source.md

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
- 2026-07-10: Added `environmental_observations.dim_bird_species_traits` with the governed exact normalization, explicit duplicate-key/match failure guards, one row per exact conformed species, every AVONET measurement/ecology/inference/dataset/dlt provenance field, and raw plus human-readable habitat-density/migration codes.
- 2026-07-10: Added `birding_agent.arizona_species_catalog` from latest `US-AZ` eBird regional membership with eBird taxonomy/order, exact optional AVONET traits, valid+reviewed+non-private activity, deterministic top-ten public-location JSON, optional GBIF/Xeno-canto aggregates/representative metadata, zero/null missing-evidence semantics, and per-source/catalog freshness.
- 2026-07-10: Hermetic SQLMesh fixtures prove exact-match traits, taxonomy-drift/hybrid unavailability, latest regional membership, private/invalid/unreviewed suppression, eleven public locations bounded to ten in deterministic order, optional evidence left joins, codebook labels, and provenance. Read-only current-source plus pinned AVONET measurement reconciled 706 catalog taxa = 624 species + 82 hybrids, with 600 species exact trait matches, 24 species unavailable, and zero hybrid matches.
- 2026-07-10: Added Soda contracts, CDM/taxonomy/ontology updates, and generated data-dictionary/lineage pages. Evidence: `.10x/evidence/2026-07-10-avonet-traits-arizona-catalog-models.md`.
- 2026-07-10: Review found per-species latest-row selection could retain taxa/taxonomy removed from newer complete snapshots and independent `MIN` location metadata could synthesize a tuple. Replaced both source selections with one deterministic latest (`_loaded_at`, `_dlt_load_id`) snapshot plus duplicate-code failure guards. Location counts/latest/notable now use partition windows while name/latitude/longitude come together from one deterministically ranked existing qualifying observation row. Fixtures prove an old-snapshot-only code is absent, conflicting public metadata resolves to the newest coherent row, a later private row cannot override it, and the 706/624/82 current baseline remains measured.
- 2026-07-10: Final independent review passed exact conformance, complete-snapshot membership, coherent public locations, privacy, optional evidence, measured coverage, contracts, and generated documentation. Review: `.10x/reviews/2026-07-10-avonet-traits-arizona-catalog-models-review.md`.
- 2026-07-10: Retrospective: append-backed replace sources require models to select one complete source snapshot, not latest rows per key; descriptive coordinates must come from one real ranked observation rather than independent aggregates. Adversarial fixtures preserve both invariants; no separate knowledge/skill record is needed.

## Blockers

None; AVONET source ingestion is complete and independently reviewed.
