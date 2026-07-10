Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-09-model-avonet-traits-and-arizona-catalog.md, .10x/specs/avonet-bird-traits-source.md, .10x/specs/arizona-bird-catalog-and-profile.md

# AVONET trait and Arizona catalog model evidence

## What was observed

- `environmental_observations.dim_bird_species_traits` renders and passes a hermetic exact-match fixture with one output row, governed normalized scientific-name conformance, code/label pairs, measurement/inference fields, and pinned AVONET/dlt provenance; an unmatched historical AVONET name does not join a current differently named species. Direct DuckDB model tests prove duplicate normalized AVONET keys fail even when unmatched and multiple conformed rows for one trait key fail rather than selecting silently.
- `birding_agent.arizona_species_catalog` renders and passes a hermetic complete-snapshot fixture in stable taxonomic/species-code order. Membership is filtered to the single latest complete `US-AZ` species-list snapshot and taxonomy to the single latest complete global taxonomy snapshot using deterministic (`_loaded_at`, `_dlt_load_id`) selection; a code present only in both older snapshots is absent. Duplicate species codes in either selected snapshot explicitly fail. Exact AVONET traits are available for the matching species; the hybrid and taxonomy-drift species remain explicit unavailable rows.
- The catalog fixture includes valid reviewed public, private, invalid, and unreviewed eBird rows. Only twelve qualifying public records contribute; private/invalid/unreviewed rows do not affect counts or JSON. Eleven public locations are counted while exactly ten are emitted in deterministic order. Conflicting public name/coordinate rows for one location resolve to the complete newest qualifying source-row tuple, and a still-newer private row for that location neither overrides nor leaks into output.
- Missing AVONET, eBird activity, GBIF, or Xeno-canto facts leave catalog membership intact with zero counts and null detail. Present GBIF/Xeno-canto facts produce deterministic aggregates, freshness, and representative recording metadata without catalog-wide media enrichment.
- A read-only measurement over the current single latest complete eBird snapshots and the exact pinned AVONET workbook produced: 706 `US-AZ` rows, 706 distinct species codes, 624 species, 82 hybrids, 600 exact species trait matches, 24 unmatched species, zero hybrid matches, and zero duplicate codes in the selected membership snapshot. No warehouse table was created or changed.

## Procedure

1. Added the two SQLMesh models, ran all SQLMesh unit tests against DuckDB fixtures, and executed the trait model directly against adversarial duplicate-key/multiple-match temporary tables to verify its explicit failure guards. After review, extended the catalog fixture with an older complete list/taxonomy snapshot containing a removed-only code and conflicting/private metadata rows for one location ID.
2. Rendered both models with the DuckDB dialect and ran a non-mutating prod diff; the diff reports exactly the two intended added models.
3. Downloaded the pinned AVONET workbook to a temporary file, parsed it under the reviewed source contract, read current eBird membership/taxonomy read-only, measured exact normalized-name coverage, then removed the workbook.
4. Added Soda contracts and regenerated/checked CDM, ontology, taxonomy, data-dictionary, and lineage artifacts.
5. Ran focused schema/contract/model tests, Ruff, MyPy, strict docs, secret scan, pre-commit, and diff/no-stage checks.

## What this supports

This supports exact-only trait conformance, one-row matched trait grain, complete trait/provenance projection, single-latest-snapshot Arizona membership/taxonomy, removal of older-only codes, duplicate-code failure, hybrid/taxonomy-drift non-mapping, privacy filtering, coherent existing-row location metadata, bounded deterministic location detail, missing-evidence preservation, source freshness, current compatibility baselines, and documentation/contract coherence.

## Limits

- The new models were not applied to prod or the live warehouse because authoritative `raw_avonet` has not been loaded there yet.
- The baseline measurement validates current source compatibility without making temporal observation/occurrence/recording counts contractual.
- No API, UI, personal-state, media enrichment, taxonomy crosswalk, or VCR repair work was performed.
- Independent final review passed and is recorded at `.10x/reviews/2026-07-10-avonet-traits-arizona-catalog-models-review.md`.
