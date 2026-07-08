---
name: create-transformation
description: "Use after generate-cdm to write SQLMesh models that transform raw dlt source tables into the Canonical Data Model."
argument-hint: "[pipeline-name]"
metadata:
  created: 2026-07-07
  updated: 2026-07-07
---

# Create transformation

Write SQLMesh models that map annotated dlt source tables to CDM dimensions and facts.

**Architecture rule:** SQLMesh is the transformation layer. dlt remains the ingestion layer. Do **not** generate `@dlt.hub.transformation` scripts for this project workflow unless the user explicitly supersedes the architecture.

Requires:

- `.schema/<cdm-name>/taxonomy.json` — confirmed table-to-concept mappings and natural keys; read `_name` from this file to determine `<cdm-name>`
- `.schema/<cdm-name>/<pipeline_name>.dbml` — annotated source schemas
- `.schema/<cdm-name>/ontology.ison` and `.schema/<cdm-name>/ontology.md` — entity graph and relationship context
- `.schema/<cdm-name>/CDM.dbml` — target Kimball CDM schema

If any are missing, run the preceding skills first: `annotate-sources`, `create-ontology`, then `generate-cdm`.

The `_name` value from `taxonomy.json` is the CDM schema/domain name unless the user explicitly chooses a different SQLMesh schema. Do not re-derive it from source system names.

This skill does **not** require a dlt MCP server. Use local project files, SQLMesh, and destination-native validation.

## Invocation arguments

Parse the appended user text as:

- `pipeline-name`: optional source pipeline to focus on, e.g. `ebird_api`

If omitted, read `taxonomy.json` for contributing pipelines. If the CDM spans multiple source pipelines, plan a cross-source SQLMesh model set under one CDM schema rather than one dlt transformation script per pipeline.

## Determine the CDM folder

If the user provides a CDM folder name, use `.schema/<cdm-name>/taxonomy.json`.

If not provided:

1. Search for `.schema/*/taxonomy.json`.
2. If exactly one exists, read it and use its `_name` as `<cdm-name>`.
3. If multiple exist, ask the user which CDM to use.
4. If none exist, stop and run the preceding skills first.

## Steps

### 1. Read inputs

Read in parallel:

- `.schema/<cdm-name>/taxonomy.json`
- `.schema/<cdm-name>/<pipeline_name>.dbml` for every contributing source pipeline
- `.schema/<cdm-name>/ontology.ison`
- `.schema/<cdm-name>/ontology.md`
- `.schema/<cdm-name>/CDM.dbml`
- relevant existing SQLMesh config under `transforms/main/config.py` and model conventions under `transforms/main/models/`

### 2. Inspect existing SQLMesh model layer

Before writing files, inspect current SQLMesh models and identify whether each is:

- **keep** — operational or still required, e.g. platform health if not superseded
- **replace** — old staging/intermediate/mart model superseded by a CDM-aligned model
- **reference** — useful SQL logic to port into the CDM models
- **remove later** — obsolete after CDM SQLMesh models validate

Do not delete old models in this skill unless the user explicitly asks. The safe default is to create the new CDM model set first, validate it, then decommission old models in a separate cleanup ticket.

### 3. Plan SQLMesh model layout

Use one SQLMesh schema/domain for the CDM, usually `<cdm-name>` from taxonomy `_name`, e.g. `environmental_observations`.

Recommended file layout:

```text
transforms/main/models/<cdm-name>/dimensions/dim_<entity>.sql
transforms/main/models/<cdm-name>/facts/fact_<process>.sql
transforms/main/models/<cdm-name>/staging/stg_<source>_<table>.sql   # only when needed
```

Rules:

- Prefer direct raw-source references from CDM models when the SQL is simple.
- Add `stg_*` models only when needed for repeated normalization, complex casts, reusable source filtering, or a clear quality boundary.
- Do not recreate the old source-specific mart layout unless the CDM explicitly calls for it.
- Use SQLMesh model names that match the CDM schema, e.g. `environmental_observations.dim_species`.

### 4. Plan transformation order

Always materialize reference/dimension models before facts because facts join to dimension surrogate keys.

Build an execution order:

1. Required staging models, if any
2. Conformed/shared dimensions
3. Non-conformed dimensions
4. Fact tables
5. Optional operational/observability models, if retained under SQLMesh

### 5. Define key strategy

Use the CDM DBML as the key contract.

For each dimension/reference table:

- Generate/populate `<entity>_sk` as the surrogate key.
- Preserve source lineage columns such as `source_id` and `source_pipeline` where specified in CDM.dbml.
- Add sentinel handling for `UNKNOWN` / `NOT_APPLICABLE` rows if the CDM requires facts to avoid NULL foreign keys.

For each fact table:

- Join to dimensions and output dimension surrogate keys, not natural keys.
- Preserve degenerate dimensions, e.g. event IDs, observation IDs, or source transaction IDs, when specified in CDM.dbml.
- Enforce the confirmed grain from CDM.dbml in the SELECT logic.

Choose a stable surrogate-key expression appropriate to the project and gateway. Prefer portable SQL where possible. If a gateway-specific function is necessary, document it in the model or use existing project SQLMesh gateway conventions.

### 6. Write SQLMesh models

For each CDM table in `.schema/<cdm-name>/CDM.dbml`, write one SQLMesh model.

Model template:

```sql
MODEL (
  name <cdm-name>.dim_species,
  kind FULL,
  description 'Dimension generated from .schema/<cdm-name>/CDM.dbml.',
  grain species_sk,
);

SELECT
  ...
FROM raw_ebird.taxonomy
```

Guidelines:

- Use source tables from annotated DBML/taxonomy, not invented tables.
- Keep SQL readable and ANSI-oriented where possible.
- Match output column names and types to `CDM.dbml`.
- Put descriptive attributes in dimensions.
- Put measures and grain columns in facts.
- Do not hide business logic in Python if SQLMesh SQL can express it clearly.
- Avoid speculative abstractions; one model file per CDM table is enough.

### 7. Add SQLMesh tests and quality hooks as needed

Add or update SQLMesh tests only for behavior that is record-backed by ontology/CDM artifacts.

Recommended checks:

- primary/surrogate keys are non-null
- grain keys are unique
- fact FK columns are non-null or use sentinel keys
- facts have plausible non-zero row counts after a full refresh

If the project uses Soda contracts for asset checks, either:

- generate/update contracts for the new CDM SQLMesh models, or
- record a follow-up ticket to add CDM quality checks after the SQLMesh model shape is ratified

Do not silently keep checks for removed legacy models.

### 8. Wire Dagster assets after model files are stable

After writing SQLMesh models, update Dagster domain wiring so the new CDM SQLMesh assets appear in lineage.

Typical updates:

- Add new `dg.AssetKey(["sqlmesh", "<cdm-name>", "dim_x"])` / `fact_x` entries.
- Remove old source-specific SQLMesh asset keys only when those models are actually removed.
- Update freshness policies/checks for CDM assets based on source cadence.
- Keep dlt ingest jobs unchanged.

### 9. Get feedback before running

Show a summary of:

- SQLMesh model files to create/update
- source tables used per CDM model
- dimensions and facts produced
- surrogate key strategy
- grain enforcement for each fact
- old SQLMesh models being referenced, retained, or proposed for later removal
- quality checks added or deferred

Ask the user to confirm before running SQLMesh.

### 10. Validate with SQLMesh and destination-native checks

After user confirmation, run finite validation commands only. Do not run long-running UI servers.

Recommended validation:

```bash
cd transforms/main && ../../.venv/bin/sqlmesh plan dev --auto-apply --no-prompts
cd transforms/main && ../../.venv/bin/sqlmesh test
```

Then use destination-native SQL for row counts, key checks, FK anti-joins, and samples. For local Quack/DuckDB, ensure no Quack writer is active before opening `data/databox.duckdb` directly.

Check:

- all expected CDM models exist
- row counts are non-zero and plausible relative to raw source tables
- surrogate keys are populated
- fact foreign keys resolve to dimension keys or sentinel rows
- no unexpected duplicate rows at the confirmed grain
- column names and types match `.schema/<cdm-name>/CDM.dbml`

If any check fails, debug SQLMesh models before presenting success.

If all checks pass, ask the user what they want next:

```text
SQLMesh CDM models validated successfully. What would you like to do next?
1. Decommission superseded legacy SQLMesh staging/mart models.
2. Add/adjust Soda quality checks for the CDM models.
3. Explore and visualise the CDM output.
```

## Output

- SQLMesh model files under `transforms/main/models/<cdm-name>/`
- optional SQLMesh tests under `transforms/main/tests/`
- optional Soda contracts under `soda/contracts/<cdm-name>/`
- Dagster SQLMesh asset wiring updates when model files are stable
