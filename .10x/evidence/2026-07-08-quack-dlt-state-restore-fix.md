Status: recorded
Created: 2026-07-08
Updated: 2026-07-08
Relates-To: .10x/tickets/done/2026-07-08-fix-quack-dlt-state-restore-in-dagster-ui.md

# Evidence: Quack dlt state restore fix

## What was observed

A Dagster UI materialize-all run failed every Quack-backed dlt source asset during dlt destination sync/state/schema reads through Quack. The error was a Quack/DuckDB attached-catalog limitation when dlt attempted to scan dlt metadata tables after the metadata moved from `main` into physical `raw_<source>` schemas.

## Procedure and results

1. Reproduced a follow-on failure from the CLI with the same `all_pipelines` asset job after disabling destination state restore:

   ```text
   Invalid Input Error: Table with name _dlt_version does not exist!
   Did you mean "raw_ebird._dlt_version, raw_noaa._dlt_version, raw_usgs._dlt_version, or raw_usgs_earthquakes._dlt_version"?
   ```

2. Confirmed the underlying Quack limitation by starting a Quack server and querying through a Quack client: even with `current_schema()` equal to `raw_ebird`, scans of `raw_ebird._dlt_version` were resolved as unqualified `_dlt_version` unless a `main._dlt_version` view existed.

3. Implemented the repair:

   - Restored `PIPELINES__RESTORE_FROM_DESTINATION=false` for Quack pipeline construction and dlt run scope.
   - For each hermetic Quack source session, publish transient `main._dlt_loads`, `main._dlt_version`, and `main._dlt_pipeline_state` views pointing at that source's physical raw metadata tables only while Quack is serving.
   - Drop those transient main views when the source session exits.
   - Pass the source raw schema into every Dagster source asset's Quack session.
   - Make `scripts/load_dlt_quack.py` use sequential hermetic Quack sessions instead of one concurrent shared Quack server.

4. Verified the Dagster all-pipelines path against the repository `.dagster` instance:

   ```bash
   DAGSTER_HOME="$PWD/.dagster" DATABOX_BACKEND=quack \
     .venv/bin/dg launch --target-path "$PWD/packages/databox" --job all_pipelines
   ```

   Result: run succeeded.

   ```text
   run_id=d17f8e8c-b272-4e66-8296-09eee0b0aaea
   RUN_SUCCESS
   ```

5. Verified definitions and CI:

   ```bash
   .venv/bin/dg check defs --use-active-venv
   task ci
   ```

   Results:

   ```text
   All definitions loaded successfully.
   pytest: 124 passed
   task ci: passed
   ```

6. Inspected the final DuckDB catalog after the successful all-pipelines run:

   ```sql
   SELECT table_schema, table_name, table_type
   FROM information_schema.tables
   WHERE (table_schema = 'main' AND table_name LIKE '\_dlt%' ESCAPE '\')
      OR (table_schema LIKE 'raw_%' AND table_type <> 'BASE TABLE');
   ```

   Result:

   ```text
   []
   ```

## What this supports

- Dagster UI materialize-all/all-pipelines can re-run Quack dlt assets after raw metadata tables already exist.
- The final physical database still has dlt metadata as raw-schema base tables, not persistent `main` tables/views.
- The transient main metadata views are a Quack client compatibility shim only during a hermetic source ingest session.

## Limits

- This evidence covers the local Quack backend. MotherDuck behavior was not live-tested.
