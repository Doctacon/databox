Status: done
Created: 2026-07-08
Updated: 2026-07-08

# Fix Quack dlt state restore failure in Dagster UI materialize-all

## Scope

Repair the regression where Dagster UI materialize-all fails Quack-backed dlt assets during dlt destination state sync with DuckDB/Quack:

```text
Not implemented Error: Multiple streaming scans or streaming scans + CTAS / insert in the same query are not currently supported
```

The fix must keep physical `raw_<source>` schemas and dlt metadata tables in `data/databox.duckdb`.

## Acceptance criteria

- Quack-backed dlt assets do not try to restore pipeline state from the destination through the Quack attached catalog.
- `_dlt_pipeline_state` remains a physical base table in each raw schema after a fresh Quack ingest.
- A Dagster all-pipelines or materialize-all style run can execute source assets without failing at dlt `step=sync`.
- `task ci` passes.

## Explicit exclusions

- Do not change the CDM/SQLMesh model layer.
- Do not switch away from Quack client-server mode.
- Do not change MotherDuck behavior.

## Progress and notes

- 2026-07-08: User reported Dagster UI materialize-all failed every dlt source asset at dlt destination state restore through Quack.
- 2026-07-08: Reproduced Quack attached-catalog scans resolving raw-schema dlt metadata as unqualified main-schema names.
- 2026-07-08: Restored Quack-scoped `PIPELINES__RESTORE_FROM_DESTINATION=false` and added transient main-schema metadata views during each hermetic source ingest session.
- 2026-07-08: Updated Dagster source assets to pass their raw schema into `quack_ingest_session(...)`.
- 2026-07-08: Changed `scripts/load_dlt_quack.py` to use sequential hermetic Quack sessions instead of a shared concurrent server.
- 2026-07-08: Verified `all_pipelines` succeeds in the repository Dagster instance (`run_id=d17f8e8c-b272-4e66-8296-09eee0b0aaea`), `dg check defs` passes, `task ci` passes with 124 tests, and no persistent `main._dlt*` or raw non-base relations remain. See `.10x/evidence/2026-07-08-quack-dlt-state-restore-fix.md`.

## Blockers

None.
