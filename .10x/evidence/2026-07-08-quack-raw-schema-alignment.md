Status: recorded
Created: 2026-07-08
Updated: 2026-07-08
Relates-To: .10x/tickets/done/2026-07-08-align-quack-raw-schemas-with-dlt-datasets.md

# Evidence: Quack raw schema alignment

## What was observed

The local Quack backend now loads each dlt source physically into its own `raw_<source>` schema in the single `data/databox.duckdb` file. dlt metadata tables are present in those raw schemas as base tables, and no dlt-loaded source tables remain in `main`.

## Procedure and results

1. Stopped the active Dagster dev process and reset local generated state:

   ```bash
   rm -rf .dagster data/databox.duckdb data/databox.duckdb.wal \
     data/sqlmesh_state.duckdb data/sqlmesh_state.duckdb.wal \
     data/.quack-clients data/dlt pipelines packages/databox/data \
     transforms/main/.cache
   ```

2. Ran a fresh full refresh:

   ```bash
   task full-refresh
   ```

   Result: passed. Final successful log:

   ```text
   .logs/full-refresh-20260708-113621.log
   ```

3. Inspected `data/databox.duckdb` with DuckDB.

   Raw schemas contained only base tables. Summary:

   ```text
   raw_base_table_count=27
   raw_non_base=[]
   main_source_relations=[]
   raw_ebird._dlt_pipeline_state=1
   raw_noaa._dlt_pipeline_state=1
   raw_usgs._dlt_pipeline_state=1
   raw_usgs_earthquakes._dlt_pipeline_state=1
   raw_usgs.daily_values=6039
   raw_usgs.sites=204
   raw_usgs._dlt_loads=1
   raw_usgs._dlt_version=1
   environmental_observations.fact_streamflow_observation=6039
   analytics.platform_health=4
   ```

4. Loaded Dagster definitions:

   ```bash
   .venv/bin/dg check defs --use-active-venv
   ```

   Result: `All definitions loaded successfully.`

5. Created the SQLMesh dev environment from prod and verified Soda contracts:

   ```bash
   cd transforms/main && ../../.venv/bin/sqlmesh --log-to-stdout --log-file-dir ../../.logs/sqlmesh plan dev --auto-apply --no-prompts --include-unmodified
   cd ../.. && .venv/bin/python scripts/verify_dev.py
   ```

   Result: SQLMesh tests passed and every active Soda contract printed `ok`.

6. Ran repository CI:

   ```bash
   task ci
   ```

   Result:

   ```text
   ruff check: passed
   ruff format --check: passed
   mypy packages/: passed
   pytest: 122 passed
   scripts/check_secrets.py .: passed
   scripts/generate_staging.py --check: passed
   scripts/generate_platform_health.py --check: passed
   ```

7. Built docs after documentation updates:

   ```bash
   task docs:build
   ```

   Result: passed with MkDocs' upstream Material warning only.

8. Cleaned safe generated artifacts:

   ```bash
   task clean
   ```

   Result: removed caches/site output while preserving `.venv`, `.env`, `.dagster`, `.logs`, and `data`.

## What this supports

- Quack still owns the single local `data/databox.duckdb` file.
- dlt source tables and dlt metadata tables now live directly under their `raw_<source>` schemas.
- The old `main.*` physical source table plus `raw_*` view shim is gone for a freshly rebuilt local DB.
- SQLMesh continues to read the same two-part raw names and remains the transformation layer.
- MotherDuck and legacy local dataset naming remain `main` inside their per-source raw databases.

## Limits

- Validation was performed on the local Quack backend. MotherDuck was preserved by code/tests but not exercised against a live MotherDuck account.
- Earlier exploratory full-refresh attempts failed before the final Taskfile helper was added; the final successful full refresh is `.logs/full-refresh-20260708-113621.log`.
