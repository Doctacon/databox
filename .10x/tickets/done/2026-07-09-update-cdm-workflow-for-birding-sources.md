Status: done
Created: 2026-07-09
Updated: 2026-07-09

# Update CDM workflow for GBIF and Xeno-canto sources

## Scope

Run the Databox source-design workflow for the new Birding Trip Copilot durable sources so `.schema` artifacts and SQLMesh transformation design stay coherent with implemented ingestion.

In scope:

- Run/update `annotate-sources` outputs for `gbif` and `xeno_canto` dlt sources.
- Update the taxonomy artifact for the chosen CDM boundary.
- Run/update ontology generation from the updated taxonomy/source DBML.
- Run/update Kimball CDM generation from the ontology.
- Reconcile resulting CDM changes with existing SQLMesh models and Soda contracts.
- Record evidence and review before commit.

Out of scope:

- Adding new external APIs.
- Changing source ingestion behavior unless the annotation/CDM workflow exposes an implementation mismatch.
- Downloading or storing Xeno-canto audio files.

## Acceptance criteria

- `.schema` includes annotated DBML for `gbif` and `xeno_canto` or records an explicit no-action rationale for excluding either source from the CDM workflow: satisfied by `.schema/environmental_observations/gbif_api.dbml` and `.schema/environmental_observations/xeno_canto_api.dbml`.
- `taxonomy.json`, `ontology.ison`, `ontology.md`, and `CDM.dbml` reflect the ratified source/CDM boundary: satisfied.
- Any SQLMesh/CDM drift is either corrected or explicitly recorded as planner-only scope: satisfied by adding `environmental_observations.fact_bird_occurrence` and `environmental_observations.fact_bird_sound_recording`; cross-source species conformance follow-up is tracked separately.
- Relevant checks pass after changes: satisfied.
- Evidence records the workflow inputs, outputs, and limits: `.10x/evidence/2026-07-09-cdm-workflow-gbif-xeno-canto.md`.

## Progress and notes

- 2026-07-09: Discovered after implementation that GBIF and Xeno-canto source ingestion and planner SQL were added, but the annotate-sources → ontology/taxonomy → CDM workflow was not rerun for those new sources. Current `.schema/environmental_observations/` contained `ebird_api.dbml`, `noaa_api.dbml`, `usgs_api.dbml`, `usgs_earthquakes_api.dbml`, `taxonomy.json`, `ontology.*`, and `CDM.dbml`, but no GBIF or Xeno-canto DBML.
- 2026-07-09: User confirmed GBIF and Xeno-canto should update the existing `.schema/environmental_observations` CDM.
- 2026-07-09: Extracted dlt schema JSON from destination `_dlt_version.schema` tables because local filesystem dlt schema JSON was absent.
- 2026-07-09: Added annotated DBML for GBIF and Xeno-canto, updated taxonomy, ontology, CDM DBML, SQLMesh CDM facts, Soda contracts, tests, and generated docs.
- 2026-07-09: Validation passed: source layout, platform health check, docs check, SQLMesh tests, `task verify`, `task ci`, and `task docs:build`.
- 2026-07-09: Review passed. Cross-source species conformance was kept as a separate semantic decision for this ticket and was later completed in `.10x/tickets/done/2026-07-09-ratify-cross-source-species-conformance.md`.

## Evidence

- `.10x/evidence/2026-07-09-cdm-workflow-gbif-xeno-canto.md`
- `.10x/reviews/2026-07-09-cdm-workflow-gbif-xeno-canto-review.md`

## Blockers

None.
