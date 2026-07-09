Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-update-cdm-workflow-for-birding-sources.md, .10x/specs/birding-agent-data-integrations.md

# Evidence: CDM workflow update for GBIF and Xeno-canto

## What was observed

The existing `.schema/environmental_observations` CDM workflow was updated for the new durable Birding Trip Copilot sources:

- GBIF occurrence source (`raw_gbif.occurrences`)
- Xeno-canto recording metadata source (`raw_xeno_canto.recordings`)

The update intentionally models GBIF occurrences and Xeno-canto recordings as separate fact entities. It does not introduce unratified cross-source species stitching between eBird, GBIF, and Xeno-canto. Xeno-canto audio remains external-link-only; the CDM stores recording metadata and URLs, not audio files.

## Procedure and results

### Source annotation

No filesystem `schemas/*.schema.json` files were present under `data/dlt/*/schemas/`, but dlt schema JSON was available in the destination `_dlt_version.schema` tables after live Quack ingestion.

Source schemas were extracted from:

- `raw_gbif._dlt_version.schema`
- `raw_xeno_canto._dlt_version.schema`

Generated annotated DBML:

- `.schema/environmental_observations/gbif_api.dbml`
- `.schema/environmental_observations/xeno_canto_api.dbml`

Confirmed annotations:

- `gbif_api.occurrences` → `BirdOccurrence`
- `xeno_canto_api.recordings` → `BirdSoundRecording`
- `_dlt_version` and `_dlt_loads` excluded for both new sources as dlt internal metadata tables.

### Taxonomy / ontology / CDM generation

Updated:

- `.schema/environmental_observations/taxonomy.json`
- `.schema/environmental_observations/ontology.ison`
- `.schema/environmental_observations/ontology.md`
- `.schema/environmental_observations/CDM.dbml`

New CDM facts:

- `environmental_observations.fact_bird_occurrence`
  - Grain: one row per GBIF bird occurrence key.
  - Preserves source identifiers, taxonomy, event date parts, coordinates, status, license, and provenance fields.
- `environmental_observations.fact_bird_sound_recording`
  - Grain: one row per Xeno-canto bird sound recording id.
  - Preserves species names, recording identifiers, location/date fields, media URLs, license, attribution, quality, and provenance fields.

### SQLMesh/Soda implementation

Added SQLMesh models:

- `transforms/main/models/environmental_observations/facts/fact_bird_occurrence.sql`
- `transforms/main/models/environmental_observations/facts/fact_bird_sound_recording.sql`

Added Soda contracts:

- `soda/contracts/environmental_observations/fact_bird_occurrence.yaml`
- `soda/contracts/environmental_observations/fact_bird_sound_recording.yaml`

Added SQLMesh unit tests for both new CDM facts in `transforms/main/tests/test_models.yaml`.

Regenerated docs dictionary:

- `docs/dictionary/environmental_observations/fact_bird_occurrence.md`
- `docs/dictionary/environmental_observations/fact_bird_sound_recording.md`
- Updated dictionary index and lineage.

### Validation commands

```bash
.venv/bin/python scripts/check_source_layout.py
.venv/bin/python scripts/generate_platform_health.py --check
.venv/bin/python scripts/generate_docs.py --check
cd transforms/main && ../../.venv/bin/sqlmesh test
```

Result:

```text
6 ok · 0 skipped · 0 failing (of 6)
platform_health.sql matches source registry
docs/dictionary/ is in sync (18 files)
8 SQLMesh tests passed
```

Full local verify:

```bash
task verify
```

Result:

```text
✓ verify done — .logs/verify-20260709-082744.log
```

Post-verify data inspection:

```text
raw_gbif.occurrences=5
raw_xeno_canto.recordings=5
environmental_observations.fact_bird_occurrence=5
environmental_observations.fact_bird_sound_recording=5
birding_agent.gbif_occurrence_evidence=5
birding_agent.xeno_canto_media_evidence=5
main._dlt* relations=0
```

Full CI:

```bash
task ci
```

Result:

```text
ruff check: passed
ruff format --check: passed
mypy packages/: passed
pytest: 145 passed, 25 warnings
coverage: 77.99% >= 70%
check_secrets.py: passed
generate_staging.py --check: passed
generate_platform_health.py --check: passed
```

Docs build:

```bash
task docs:build
```

Result:

```text
Generated 16 model pages + lineage + index under docs/dictionary/
mkdocs build --strict: passed
```

MkDocs emitted its existing informational warnings about MkDocs 2.0 and unnaved dictionary pages; build completed successfully.

## What this supports

- The annotate-sources → taxonomy/ontology → CDM workflow is now up to date for GBIF and Xeno-canto within the existing `environmental_observations` CDM boundary.
- The SQLMesh CDM implementation now includes GBIF and Xeno-canto facts, not only planner-layer raw views.
- The local Quack raw schema layout remains clean: no persistent `main._dlt*` relations.
- Existing source jobs, SQLMesh planning, docs, and CI remain green.

## Limits

- Source annotation used dlt schema JSON stored in destination `_dlt_version.schema` tables because local filesystem dlt schema JSON files were absent.
- At the time of this CDM workflow update, GBIF/Xeno-canto species fields were not stitched into a conformed cross-source `dim_species` natural key. That follow-up semantic decision and implementation was later completed in `.10x/tickets/done/2026-07-09-ratify-cross-source-species-conformance.md`.
- Xeno-canto was verified in smoke mode (`DATABOX_SMOKE=1`, 5 rows), not as a full historical load.
