Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Target: .10x/tickets/done/2026-07-09-model-avonet-traits-and-arizona-catalog.md
Verdict: pass

# AVONET traits and Arizona catalog model review

## Target

`environmental_observations.dim_bird_species_traits`, `birding_agent.arizona_species_catalog`, contracts, schemas, generated documentation, and tests.

## Findings

- AVONET normalization exactly follows governed scientific-name conformance. Duplicate normalized source keys and multiple conformed matches fail explicitly; all trait/measurement/inference/dataset/dlt provenance and code labels are preserved.
- Catalog membership derives from one deterministic latest complete eBird `US-AZ` list snapshot and one latest complete taxonomy snapshot. Old-only taxa and duplicate codes cannot survive silently.
- Exact trait joins leave 24 current taxonomy-drift species and all 82 hybrids explicitly unavailable; no common-name/parent guess exists.
- Valid/reviewed/non-private filtering protects location output. Counts/latest/notable aggregate over qualifying rows while name/latitude/longitude come from one coherent deterministic source row. Top-ten JSON remains bounded and stable.
- Optional AVONET/eBird/GBIF/Xeno absence never removes catalog rows and preserves zero/null semantics.
- The exact pinned workbook/read-only source baseline independently reproduces 706 taxa, 624 species, 82 hybrids, 600 exact species matches, 24 unmatched species, and zero hybrid matches.
- Thirteen SQLMesh tests, focused Python/schema tests, Ruff, nonmutating production diff, contracts, and generated artifacts passed.

## Resolved findings

Initial review found old-only regional taxa survived because rows were selected per species rather than per complete snapshot, and independently aggregated location metadata could form a tuple never observed. Final models use complete-snapshot selection with duplicate guards and coherent ranked source rows; adversarial fixtures prove both repairs.

## Verdict

Pass. No model blocker remains.

## Residual risk

AVONET v7 uses an older eBird taxonomy. Exact unmatched rows remain visible until a reviewed newer release or evidence-backed crosswalk is introduced.
