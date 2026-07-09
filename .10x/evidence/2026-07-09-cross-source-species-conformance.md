Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-ratify-cross-source-species-conformance.md, .10x/decisions/cross-source-bird-species-conformance.md

# Evidence: Cross-source species conformance

## What was observed

The `environmental_observations` CDM now conforms species across eBird, GBIF, and Xeno-canto in `environmental_observations.dim_species`.

Ratified conformance contract:

- Sources: eBird, GBIF, and Xeno-canto.
- Natural key: normalized scientific name.
- Normalization: lowercase, trim, and strip trailing parenthetical authorship; do not collapse hybrids/subspecies unless source scientific-name text matches after author stripping.
- Precedence: eBird wins descriptive attributes, GBIF fills taxon identifiers/gaps, Xeno-canto supplies media context.
- Coverage: union of species from any source.

## Procedure and results

Updated durable decision/spec artifacts:

- `.10x/decisions/cross-source-bird-species-conformance.md`
- `.schema/environmental_observations/taxonomy.json`
- `.schema/environmental_observations/ontology.ison`
- `.schema/environmental_observations/ontology.md`
- `.schema/environmental_observations/CDM.dbml`

Updated implementation artifacts:

- `transforms/main/models/environmental_observations/dimensions/dim_species.sql`
- `transforms/main/models/environmental_observations/facts/fact_bird_observation.sql`
- `transforms/main/models/environmental_observations/facts/fact_bird_occurrence.sql`
- `transforms/main/models/environmental_observations/facts/fact_bird_sound_recording.sql`
- `transforms/main/models/birding_agent/planner/species_lookup.sql`
- `soda/contracts/environmental_observations/dim_species.yaml`
- `soda/contracts/environmental_observations/fact_bird_occurrence.yaml`
- `soda/contracts/environmental_observations/fact_bird_sound_recording.yaml`
- `transforms/main/tests/test_models.yaml`

Validation:

```bash
cd transforms/main && ../../.venv/bin/sqlmesh test
```

Result:

```text
10 SQLMesh tests passed
```

The SQLMesh unit tests cover a clean eBird/GBIF/Xeno-canto match, an eBird duplicate normalized-name input that must not duplicate `species_sk`, source-scoped fallback dimension rows for GBIF/Xeno-canto records that lack usable scientific-name keys, a GBIF fact fallback case where blank `accepted_scientific_name` must fall through to `scientific_name` while a no-name row remains source-scoped, and an eBird observation fact case proving a natural-key match does not also join a source-scoped fallback row.

```bash
task verify
```

Result:

```text
✓ verify done — .logs/verify-20260709-093407.log
```

Post-verify DuckDB inspection:

```text
environmental_observations.dim_species=17761 rows
species rows with GBIF context=5
species rows with Xeno-canto context=3
duplicate species_sk groups=0
environmental_observations.fact_bird_occurrence=5 rows, 5 distinct species_sk, 0 UNKNOWN species_sk
environmental_observations.fact_bird_sound_recording=5 rows, 3 distinct species_sk, 0 UNKNOWN species_sk
duplicate fact_bird_observation source_observation_id groups=0
birding_agent.species_lookup=17760 rows
main._dlt* relations=0
```

Representative conformed GBIF matches after stripping GBIF authorship:

```text
Aythya valisineria -> eBird Canvasback + GBIF accepted_taxon_key 2498256
Nycticorax nycticorax -> eBird Black-crowned Night Heron + GBIF accepted_taxon_key 2480863
Pyrocephalus rubinus -> eBird Vermilion Flycatcher + GBIF accepted_taxon_key 2483647
Spatula clypeata -> eBird Northern Shoveler + GBIF accepted_taxon_key 8332393
```

Representative Xeno-canto matches:

```text
Anser caerulescens -> eBird Snow Goose + 1 Xeno-canto recording
Branta canadensis -> eBird Canada Goose + 2 Xeno-canto recordings
Dendrocygna autumnalis -> eBird Black-bellied Whistling-Duck + 2 Xeno-canto recordings
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

DeepEval suite:

```bash
task eval:agent
```

Result:

```text
2 passed
Pass Rate: 100.0%
```

## What this supports

- `dim_species` is now a conformed dimension across the three ratified bird sources.
- GBIF and Xeno-canto facts reference conformed `species_sk` values rather than remaining disconnected source-scoped evidence.
- Planner species lookup now reads the conformed species dimension.
- Existing source ingest, SQLMesh planning, docs, CI, and agent evals remain green.

## Limits

- The normalized scientific-name rule strips trailing parenthetical authorship but does not implement a full taxonomy synonym/crosswalk service.
- Hybrids and subspecies remain separate unless their normalized source scientific-name text matches exactly after author stripping.
- Xeno-canto was still validated in smoke mode with 5 rows, not as a full historical media metadata load.
