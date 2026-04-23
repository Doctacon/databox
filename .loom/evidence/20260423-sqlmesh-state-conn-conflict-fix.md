---
id: evidence:sqlmesh-state-conn-conflict-fix
kind: evidence
status: accepted
created_at: 2026-04-23T01:10:00Z
updated_at: 2026-04-23T01:10:00Z
scope:
  kind: workspace
links:
  ticket: ticket:sqlmesh-state-conn-conflict
---

# Summary

`task verify` runs green on a clean `data/` dir under both backends after the fix.

# Fix

Two changes in `packages/databox/`:

1. `config/settings.py::sqlmesh_config()` now registers only the gateway matching `settings.backend` (plus a dedicated `state_connection` pointing at `data/sqlmesh_state.duckdb`). Previously both `local` and `motherduck` gateways were registered, and SQLMesh's `Context.engine_adapters` property builds an `EngineAdapter` for each — which made `DATABOX_BACKEND=local` still open a MotherDuck connection.
2. `orchestration/_factories.py::ensure_motherduck_databases()` now opens `duckdb.connect(database=..., config={"custom_user_agent": f"SQLMesh/{__version__}"})` — matching the kwargs SQLMesh later passes. DuckDB caches a process-global handle per `md:?motherduck_token=...` URL and rejects subsequent opens with mismatched config dicts ("Can't open a connection to same database file with a different configuration than existing connections").

# Evidence

Both runs issued on clean `data/` directory (`rm -rf data/*.duckdb` beforehand). Smoke mode (`DATABOX_SMOKE=1`) caps each dlt source to 5 items.

## `DATABOX_BACKEND=motherduck`

```
2026-04-22 18:07:59 -0700 - dagster - DEBUG - __ASSET_JOB - d40f7276-36b2-499b-93f5-4f864b4a582c - 97583 - sqlmesh__usgs_staging__stg_usgs_sites_soda_contract - STEP_SUCCESS - Finished execution of step "sqlmesh__usgs_staging__stg_usgs_sites_soda_contract" in 833ms.
2026-04-22 18:08:00 -0700 - dagster - DEBUG - __ASSET_JOB - d40f7276-36b2-499b-93f5-4f864b4a582c - 92958 - ENGINE_EVENT - Multiprocess executor: parent process exiting after 1m15s (pid: 92958)
2026-04-22 18:08:00 -0700 - dagster - DEBUG - __ASSET_JOB - d40f7276-36b2-499b-93f5-4f864b4a582c - 92958 - RUN_SUCCESS - Finished execution of run for "__ASSET_JOB".
```

## `DATABOX_BACKEND=local`

```
2026-04-22 18:09:27 -0700 - dagster - DEBUG - __ASSET_JOB - 27145bad-f993-4a53-b5d5-022f3fd5dd68 - 3439 - sqlmesh__usgs_staging__stg_usgs_sites_soda_contract - STEP_SUCCESS - Finished execution of step "sqlmesh__usgs_staging__stg_usgs_sites_soda_contract" in 859ms.
2026-04-22 18:09:28 -0700 - dagster - DEBUG - __ASSET_JOB - 27145bad-f993-4a53-b5d5-022f3fd5dd68 - 98461 - ENGINE_EVENT - Multiprocess executor: parent process exiting after 1m16s (pid: 98461)
2026-04-22 18:09:28 -0700 - dagster - DEBUG - __ASSET_JOB - 27145bad-f993-4a53-b5d5-022f3fd5dd68 - 98461 - RUN_SUCCESS - Finished execution of run for "__ASSET_JOB".
```

## Lint + type

```
$ .venv/bin/ruff check packages/ transforms/
All checks passed!

$ .venv/bin/mypy packages/
Success: no issues found in 50 source files
```

## Test suite

`118 passed, 1 failed` — the failing test is `packages/databox-sources/tests/ebird/test_idempotency.py::test_ebird_recent_observations_idempotent`, explicitly out-of-scope per the ticket's "Out of Scope" section. Passes in isolation; fails only when run together with other tests — ordering flake, not regression from this fix.

# Residual risk

- The ensure-function now depends on SQLMesh's exported `__version__` to match the user-agent string. If SQLMesh changes the user-agent key name or structure, this fix silently regresses into the original conflict. Low risk — the config key has been stable since at least SQLMesh 0.100.
- The single-gateway config means switching `DATABOX_BACKEND` mid-process does not pick up the new gateway until re-import. Acceptable — every consumer (Dagster subprocess, SQLMesh CLI) reads the backend once at startup.
