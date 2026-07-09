Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-update-cdm-workflow-for-birding-sources.md
Verdict: pass

# Review: CDM workflow update for GBIF and Xeno-canto

## Target

Uncommitted CDM workflow update for GBIF and Xeno-canto in the existing `environmental_observations` CDM boundary.

Reviewed scope:

- `.schema/environmental_observations/gbif_api.dbml`
- `.schema/environmental_observations/xeno_canto_api.dbml`
- `.schema/environmental_observations/taxonomy.json`
- `.schema/environmental_observations/ontology.ison`
- `.schema/environmental_observations/ontology.md`
- `.schema/environmental_observations/CDM.dbml`
- `transforms/main/models/environmental_observations/facts/fact_bird_occurrence.sql`
- `transforms/main/models/environmental_observations/facts/fact_bird_sound_recording.sql`
- `soda/contracts/environmental_observations/fact_bird_occurrence.yaml`
- `soda/contracts/environmental_observations/fact_bird_sound_recording.yaml`
- `transforms/main/tests/test_models.yaml`

## Findings

### Pass: Source annotations present and aligned

GBIF and Xeno-canto schema artifacts are present and align with the source contracts:

- `.schema/environmental_observations/gbif_api.dbml`
- `.schema/environmental_observations/xeno_canto_api.dbml`

The DBML annotates `gbif_api.occurrences` as `BirdOccurrence` and `xeno_canto_api.recordings` as `BirdSoundRecording`, while excluding dlt internal tables.

### Pass: CDM boundary avoids unratified species stitching

The update models GBIF occurrences and Xeno-canto recordings as separate facts with no unratified cross-source species natural key. This is consistent with the active Birding Agent data integration spec requirement to preserve species/taxonomy/media evidence while avoiding model-generated inferred attributes not present in sources or ratified use cases.

### Pass: SQLMesh facts preserve required fields

The new SQLMesh facts preserve required identifiers, taxonomy, location/date, provenance, license, and media-link fields:

- `environmental_observations.fact_bird_occurrence`
- `environmental_observations.fact_bird_sound_recording`

Xeno-canto media remains represented as external links only; no audio storage behavior was introduced.

### Pass: Contracts and tests added

Soda contracts cover core key uniqueness/non-null and row-count checks. SQLMesh unit tests were added for both new facts and the full SQLMesh unit suite passed with 8 tests.

### Closure note resolved

The fresh reviewer initially identified one closure blocker: no durable evidence record existed yet for this workflow. Evidence has since been recorded in `.10x/evidence/2026-07-09-cdm-workflow-gbif-xeno-canto.md`.

## Verdict

Pass.

## Residual risk

- Cross-source species conformance was intentionally unresolved for this review scope and was later completed in `.10x/tickets/done/2026-07-09-ratify-cross-source-species-conformance.md`.
- Source annotation used dlt schema JSON from destination `_dlt_version.schema` because filesystem dlt schema JSON files were absent.
