---
id: ticket:sqlmesh-state-conn-conflict
kind: ticket
status: complete_pending_acceptance
created_at: 2026-04-23T00:20:00Z
updated_at: 2026-04-23T01:15:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 5
  evidence: evidence:sqlmesh-state-conn-conflict-fix
depends_on: []
---

# Goal

Fix the DuckDB connection-config conflict that breaks SQLMesh state-schema initialization on first run. The `sqlmesh_project` asset currently fails before any model materializes, taking every downstream asset (SQLMesh marts + Soda contracts + freshness checks + analytics) with it.

# Why

Reproduced 2026-04-23 running `task verify` (smoke mode) and a raw `DATABOX_BACKEND=local ... dagster asset materialize --select '*' -m databox.orchestration.definitions`. Both runs fail at the same step with:

```
Failed to create schema 'sqlmesh': Connection Error: Can't open a connection
to same database file with a different configuration than existing connections
```

Stack trace bottoms out at `sqlmesh/utils/connection_pool.py:296` in `self._connection_factory()` → `duckdb.connect()`. DuckDB throws this when the same `.duckdb` file is opened twice in one process with conflicting configs (read-only vs read-write, or different extension sets).

Happens in both `DATABOX_BACKEND=local` and `DATABOX_BACKEND=motherduck`. MotherDuck also warns "The motherduck engine is not recommended for storing SQLMesh state in production deployments" — but the local-mode failure proves the root cause is not MotherDuck-specific.

Last successful pipeline run was 2026-04-21 23:45 (run `3e500a0b`, commit `3e500a0b`-era). No intentional SQLMesh / DuckDB upgrade between then and now. The regression coincides with the strict-mypy commit (`7e37296`), which hid the failure behind a loader crash (`dg.AssetExecutionContext` validator rejection). Once the loader was fixed (commit `56307ed`), the runtime conflict surfaced — but the state-conn conflict itself was likely latent well before that.

A staff-level reviewer running `task verify` on a fresh clone will hit this on attempt one. The entire "working end-to-end" portfolio claim depends on this step.

# In Scope

- Reproduce on a clean `data/` directory (no prior SQLMesh state)
- Identify which connection is opening `data/databox.duckdb` with which config, and who's opening it a second time with a different one
- Likely fix sites:
  - `packages/databox/databox/config/settings.py::sqlmesh_config()` — currently attaches all `raw_*` + `databox` catalogs to one `DuckDBConnectionConfig` with the `h3` extension. SQLMesh state backend may be opening `databox.duckdb` again without the same extension list.
  - Add an explicit `state_connection` to the gateway config pointing to a dedicated state DB (e.g., `data/sqlmesh_state.duckdb`) so state operations never touch the data catalogs. SQLMesh docs specifically recommend this pattern for DuckDB.
  - Alternative: move state to a separate gateway entirely, still on-disk but with no extensions attached.
- For the MotherDuck gateway: same pattern — put state on a local DuckDB file, not in MotherDuck. This also satisfies the SQLMesh warning.
- Add a smoke regression test or CI job that runs `task verify` against a fresh `data/` dir and asserts `sqlmesh_project` succeeds.

# Out of Scope

- Replacing SQLMesh (it's the transform layer of the stack — no)
- Downgrading SQLMesh or DuckDB versions
- Moving state to Postgres (adds infra; the single-operator stack shouldn't require a server)
- Fixing unrelated pipeline flakes (`ebird/test_idempotency.py`, etc. — separate concern)

# Acceptance Criteria

- `task verify` completes with `sqlmesh_project` green against both `DATABOX_BACKEND=local` and `DATABOX_BACKEND=motherduck`
- Fresh clone + `task install` + `task verify` produces a green smoke run with no manual DB surgery
- `pyproject.toml` / `settings.py` change is minimal and documented
- If the fix is a dedicated `state_connection`, the new state-DB path is listed in `task db:reset` so `db:reset` keeps working
- A short note in `docs/architecture.md` or similar explains *why* state lives where it does (so future contributors don't undo it)

# Approach Notes

1. Reproduce on clean `data/` dir: `task clean-all && task install && task verify`
2. Confirm the error. Capture the full stack.
3. Read `sqlmesh/utils/connection_pool.py` + `sqlmesh/core/state_sync/db/facade.py` to confirm which config is being used for state
4. Add `state_connection=DuckDBConnectionConfig(database=str(DATA_DIR / "sqlmesh_state.duckdb"))` to each `GatewayConfig` in `sqlmesh_config()`
5. Add `data/sqlmesh_state.duckdb` to `task db:reset` rm list
6. Re-run smoke. Verify green.
7. Add the state DB path to `.gitignore` check if not already covered by `data/**`

# Evidence Expectations

- Green `task verify` log committed to `.loom/evidence/` (or linked from there)
- Green `task verify` with `DATABOX_BACKEND=motherduck` set (requires `MOTHERDUCK_TOKEN`; may need to run locally and paste)
- `uv run ruff check .` + `uv run mypy packages/` clean after the fix

# Resolution

See `evidence:sqlmesh-state-conn-conflict-fix` (`.loom/evidence/20260423-sqlmesh-state-conn-conflict-fix.md`).

Two-part fix in `packages/databox/`:

1. `config/settings.py::sqlmesh_config()` — register only the gateway matching `settings.backend` (not both). SQLMesh's `Context.engine_adapters` eagerly builds an `EngineAdapter` for every gateway in `Config.gateways`, so registering both made `DATABOX_BACKEND=local` still open a MotherDuck connection. Dedicated `state_connection` on `data/sqlmesh_state.duckdb` retained on both paths.
2. `orchestration/_factories.py::ensure_motherduck_databases()` — opens `duckdb.connect(database=..., config={"custom_user_agent": f"SQLMesh/{__version__}"})` so the md: URL config matches SQLMesh's later open. DuckDB caches a process-global handle per `md:?motherduck_token=...` URL and rejects subsequent opens with mismatched config dicts.

Both `DATABOX_BACKEND=local` and `DATABOX_BACKEND=motherduck` smoke runs end with `RUN_SUCCESS` on a clean `data/` directory. Ruff + mypy clean. Pytest: 118 passed, 1 flake (`ebird/test_idempotency.py` — explicitly out of scope).

`task db:reset` (Taskfile.yaml:86) already lists `data/sqlmesh_state.duckdb` explicitly — no change needed there. Architecture note lives in `docs/configuration.md` ("SQLMesh state" section, lines 50–67).
