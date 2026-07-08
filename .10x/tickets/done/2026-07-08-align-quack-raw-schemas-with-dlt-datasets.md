Status: done
Created: 2026-07-08
Updated: 2026-07-08

# Align Quack raw schemas with dlt datasets

## Scope

Change the local Quack backend so each dlt source physically loads into its own raw schema inside the single `data/databox.duckdb` file, matching the operator mental model:

```text
raw_ebird.*
raw_noaa.*
raw_usgs.*
raw_usgs_earthquakes.*
```

Each raw schema should contain the source tables and dlt metadata tables directly, including `_dlt_loads`, `_dlt_version`, and `_dlt_pipeline_state` when dlt creates them. The current `main.*` physical table plus `raw_*` view shim should be removed from the Quack path.

## Explicit exclusions

- Do not replace Quack with direct multi-process DuckDB opens.
- Do not change SQLMesh as the transformation layer.
- Do not change MotherDuck raw dataset naming unless required to preserve behavior.
- Do not push the commit.

## Acceptance criteria

- `settings.raw_dataset_name(name)` returns `raw_<name>` for `DATABOX_BACKEND=quack` and preserves `main` for MotherDuck/legacy per-source-file backends.
- Quack post-load dedupe operates on physical `raw_<source>.<table>` base tables.
- Quack no longer publishes `raw_*` views over `main.*`.
- Legacy raw views are dropped safely before a Quack server starts, so existing local DBs can migrate without object-name conflicts.
- Local state is reset and a fresh `task full-refresh` produces raw source base tables in `data/databox.duckdb`.
- Verification confirms source tables and dlt metadata live under `raw_*`, and no dlt-loaded source tables remain in `main`.
- `task ci` and `task full-refresh` pass.
- Changes are committed on `main` and not pushed.

## Progress and notes

- 2026-07-08: User explicitly requested execution and local commit without push.
- 2026-07-08: Changed Quack dlt dataset naming to physical `raw_<source>` schemas while preserving `main` datasets for MotherDuck and legacy local per-source files.
- 2026-07-08: Removed raw view publishing and changed Quack dedupe to operate on physical raw base tables.
- 2026-07-08: Added legacy raw-view dropping before Quack serve so existing local DBs can migrate.
- 2026-07-08: Restored destination pipeline-state sync for Quack so `_dlt_pipeline_state` is created under each raw schema.
- 2026-07-08: Added `scripts/sqlmesh_plan_prod.sh` so `task full-refresh`/`task verify` work from a fresh SQLMesh state DB and still restate when prod exists.
- 2026-07-08: Reset local generated state and ran fresh `task full-refresh`; raw source and dlt metadata tables are base tables under `raw_*`, with no source tables in `main`. See `.10x/evidence/2026-07-08-quack-raw-schema-alignment.md`.
- 2026-07-08: `dg check defs`, SQLMesh dev plan, Soda verification, docs build, and `task ci` passed. Review verdict: pass.

## Blockers

None.
