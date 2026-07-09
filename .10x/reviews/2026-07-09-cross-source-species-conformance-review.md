Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-ratify-cross-source-species-conformance.md
Verdict: pass

# Review: Cross-source species conformance

## Target

Implementation of `.10x/tickets/done/2026-07-09-ratify-cross-source-species-conformance.md` and `.10x/decisions/cross-source-bird-species-conformance.md`.

Reviewed scope:

- `.schema/environmental_observations/taxonomy.json`
- `.schema/environmental_observations/ontology.ison`
- `.schema/environmental_observations/ontology.md`
- `.schema/environmental_observations/CDM.dbml`
- `transforms/main/models/environmental_observations/dimensions/dim_species.sql`
- `transforms/main/models/environmental_observations/facts/fact_bird_observation.sql`
- `transforms/main/models/environmental_observations/facts/fact_bird_occurrence.sql`
- `transforms/main/models/environmental_observations/facts/fact_bird_sound_recording.sql`
- `transforms/main/models/birding_agent/planner/species_lookup.sql`
- `soda/contracts/environmental_observations/dim_species.yaml`
- `transforms/main/tests/test_models.yaml`
- generated docs dictionary pages

## Findings

### Initial review blockers resolved

Earlier review found:

- GBIF no-name fallback could join multiple rows when several source rows shared a taxon key.
- Blank `accepted_scientific_name` did not fall through to `scientific_name`.
- eBird fact joins could duplicate rows by joining both normalized natural key and source-id fallback.
- Tests covered happy paths but not fallback/duplicate cases.

Final implementation resolves these:

- GBIF blank-string fallback applies `NULLIF(TRIM(...), '')` before falling through from `accepted_scientific_name` to `scientific_name` to `species`.
- GBIF no-name fallback is source-row scoped by GBIF `key`, and fact fallback joins only when the normalized natural key is null.
- Xeno-canto no-name fallback is source-row scoped by recording `id`, null/blank safe, and fact fallback is guarded.
- eBird duplicate normalized-name dimension rows are deduped by `ROW_NUMBER() ... PARTITION BY conformed_key`.
- eBird observation fact source-id fallback only applies when normalized `sci_name` is null.
- SQLMesh unit tests cover duplicate eBird normalized names, source-scoped fallback dimension rows, GBIF blank-name fact fallback, and eBird fact duplicate-join prevention.

### Contract alignment

The implementation matches the ratified contract:

- Sources: eBird, GBIF, and Xeno-canto.
- Natural key: normalized scientific name.
- Normalization: lowercase, trim, strip trailing parenthetical authorship.
- Precedence: eBird first, GBIF fills taxon identifiers/gaps, Xeno-canto supplies media context.
- Coverage: union of all sources.
- Xeno-canto audio remains external-link-only.

## Verdict

Pass / closure-ready.

## Residual risk

- The normalized scientific-name rule is intentionally lightweight and is not a full taxonomic synonym/crosswalk service.
- Hybrid/subspecies conformance remains exact-text-based after author stripping; this avoids unratified broad taxonomic collapsing.
