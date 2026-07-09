Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-implement-shared-quack-parallel-refresh.md
Verdict: pass

# Review: Parallel Quack local refresh

## Target

Implementation of `.10x/specs/parallel-quack-local-refresh.md` and `.10x/tickets/done/2026-07-09-implement-shared-quack-parallel-refresh.md`.

## Findings

Initial review found these closure blockers:

1. standalone source sessions left `.quack-clients` behind,
2. overlap was measured from `dg launch` process lifetimes rather than actual ingest sessions,
3. partial `QuackServer.__enter__` failure could leak its connection/transient views,
4. dedupe/cleanup errors could mask source failure attribution,
5. existing six source schedules were omitted when the parallel schedule was added,
6. refresh output did not directly validate/report raw counts and persistent `main._dlt*`,
7. incremental-loading documentation still described sequential source runs.

All were repaired:

- standalone cleanup now runs in `finally` and is tested for success/failure,
- source processes emit atomic cross-process timeline artifacts around `quack_ingest_session`; overlap gates consume those actual intervals and reject non-overlap,
- partial server startup closes the connection and removes transient metadata views,
- source failures remain the primary `ParallelRefreshError` while maintenance errors are preserved as cause/notes,
- all source schedules plus the parallel schedule are registered,
- refresh inspection reports core row counts and requires zero persistent `main._dlt*`,
- active runbook/incremental-loading text describes the concurrent shared-server path.

Two consecutive live smoke refreshes passed with all six source jobs, actual ingest overlap, stable core counts, zero `main._dlt*`, and SQLMesh completion. Full CI passed with 153 tests.

## Verdict

Pass / closure-ready.

## Residual risk

Quack is beta and dlt's unqualified metadata reads require transient union-by-name compatibility views. The behavior is covered by unit tests and consecutive live smoke runs, but an upstream Quack/dlt change may require revisiting this adapter.
