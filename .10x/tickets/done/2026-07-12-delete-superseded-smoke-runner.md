Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md
Depends-On: .10x/tickets/done/2026-07-12-audit-warehouse-repository-simplicity.md

# Delete superseded smoke runner

## Scope

Delete unreferenced `scripts/smoke.py`, which duplicates the canonical
Dagster/Quack refresh path, and repair only stale ownership prose that names it.
Do not replace it with another wrapper.

## Acceptance criteria

- `scripts/smoke.py` is removed.
- No active Taskfile, CI, docs, package, test, or import reference remains.
- Canonical smoke/full-refresh ownership remains `task verify` /
  `task full-refresh`, `scripts/load_dlt_quack.py`, and the reviewed parallel
  refresh lifecycle.
- Source registry/parallel refresh/runner tests, definitions loading, static
  checks, and command-shape inspection pass without running a live refresh.

## Explicit exclusions

- Executing `task verify`, refreshes, SQLMesh apply, or warehouse operations
- Refactoring the canonical refresh lifecycle
- Deleting migration scripts or other thin intentional CLI boundaries

## Evidence expectations

Record reference proof, deletion, canonical owner paths, non-live verification,
and independent review.

## Progress and notes

- 2026-07-12: Opened from the high-confidence duplicate-runner finding in the
  warehouse simplicity audit.
- 2026-07-12: Deleted only unreferenced `scripts/smoke.py`; no replacement was added. Repaired the source-registry docstring to name current registry-derived Dagster composition, refresh eligibility, source CI, freshness, and platform-health responsibilities.
- 2026-07-12: Exact active reference scan found zero remaining `scripts/smoke.py` consumers. Command-shape inspection proves `task full-refresh`/`task verify` both use `scripts/load_dlt_quack.py` → `execute_parallel_refresh`, with smoke mode injected only by verify.
- 2026-07-12: Registry/parallel-refresh/refresh-runner tests passed 39/39; Dagster Definitions, Ruff, format, focused MyPy, diff, and empty staging checks passed. Evidence: `.10x/evidence/2026-07-12-superseded-smoke-runner-deletion.md`.
- 2026-07-12: Independent review `.10x/reviews/2026-07-12-superseded-smoke-runner-deletion-review.md` passed every criterion. Retrospective: an unreferenced alternate orchestration path is harmful duplication even when small; the canonical Task/Quack path remains singular. Ticket closed.

## Blockers

None.
