Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-delete-superseded-smoke-runner.md, .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md

# Superseded smoke runner deletion

## What was observed

`scripts/smoke.py` was an unreferenced, second in-process orchestration path. It
constructed its own Dagster `Definitions`, dlt/SQLMesh resources, and global
asset job rather than using the canonical shared-Quack lifecycle.

Exact active-tree scanning found its only active mention in the source-registry
module docstring. No Taskfile, CI, docs, package, script, test, or import
consumer existed.

## Change

- Deleted `scripts/smoke.py` without adding a replacement.
- Repaired the `databox.config.sources` module docstring to name current
  registry-derived responsibilities: Dagster source composition, refresh
  eligibility, source CI, freshness policies, and platform-health SQL.

Canonical command ownership remains:

- `task full-refresh` and `task verify` in `Taskfile.yaml`;
- both invoke `scripts/load_dlt_quack.py`;
- that script calls `execute_parallel_refresh` in
  `databox.orchestration.parallel_refresh`;
- `task verify` alone injects `DATABOX_SMOKE=1`.

## Procedure and results

- Exact `scripts/smoke.py` scan across Taskfile, `.github`, docs, packages,
  scripts, tests, and root package metadata — zero active matches after repair.
- Command-shape assertion over parsed `Taskfile.yaml` and
  `scripts/load_dlt_quack.py` — both canonical commands target
  `load_dlt_quack.py`; only verify sets smoke mode; the loader calls
  `execute_parallel_refresh`.
- `.venv/bin/pytest --no-cov -q tests/test_source_registry.py tests/test_parallel_refresh.py tests/test_source_refresh_runner.py` — **39 passed**.
- `.venv/bin/dg check defs --use-active-venv` — all definitions loaded.
- Focused Ruff check — passed; Ruff format check — seven files already
  formatted.
- Focused MyPy over registry, loader, parallel refresh, and refresh runner — no
  issues in four source files.
- `git diff --check` — passed.
- `git diff --cached --name-only` — empty.

## What this supports

This supports deletion of only the proven duplicate runner, correction of its
single stale active ownership reference, and preservation of the canonical
registry-derived Dagster/Quack source lifecycle.

## Limits

No live `task verify`, full refresh, provider request, SQLMesh command/apply,
shared warehouse access, model call, email, application action, staging,
commit, or push occurred. Passing unit/definition checks prove local contract
coherence, not live provider availability.
