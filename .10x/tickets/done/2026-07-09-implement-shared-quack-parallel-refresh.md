Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-build-local-birding-copilot-product.md
Depends-On: .10x/tickets/done/2026-07-09-decommission-motherduck-platform-support.md

# Implement shared-server parallel Quack refresh

## Scope

Implement `.10x/specs/parallel-quack-local-refresh.md` across Quack lifecycle, Dagster/full-refresh orchestration, tests, tasks, and docs.

The executor MUST first reproduce and understand current Quack/dlt metadata behavior under two concurrent source clients. Then implement one server lifecycle and safe independent source clients if the protocol supports the required contract.

## Explicit exclusions

- Do not silently retain or restore sequential source execution.
- Do not introduce direct multi-process DuckDB file writes.
- Do not model `_dlt_*` tables as Dagster assets.
- Do not modify agent/model/UI behavior.

## Acceptance criteria

- Exactly one Quack server owns `data/databox.duckdb` for a full refresh.
- At least two registered source clients have overlapping observed load intervals.
- Every registered source remains independently runnable and hermetic.
- Source data and `_dlt_*` metadata remain physical under source-specific `raw_<source>` schemas.
- Repeat refreshes restore state or otherwise behave idempotently without persistent `main._dlt*` relations.
- A source failure prevents SQLMesh and returns a failing overall result while cleanup succeeds.
- Full refresh runs SQLMesh only after all required source loads succeed.
- Tests cover lifecycle, overlap, failure propagation, cleanup, and source isolation.
- A smoke run records raw row counts and no `main._dlt*` relations.

If safe concurrency cannot be achieved with the installed Quack/dlt behavior, the ticket MUST be marked blocked with a minimal reproducible procedure and raw failure evidence. Sequential fallback is not acceptance.

## Evidence expectations

Record:

- concurrency timeline/overlap evidence,
- one-server start/stop evidence,
- repeat-run state evidence,
- raw-schema and `_dlt_*` inspection,
- failing-source behavior,
- relevant unit/integration/full-refresh output.

## Progress and notes

- 2026-07-09: Reproduced Quack concurrency with two independent dlt clients. First loads succeeded concurrently; repeat loads exposed dlt's unqualified `_dlt_version` lookup through the attached catalog.
- 2026-07-09: Implemented one shared server plus transient union-by-name `main._dlt*` read views over source-scoped physical metadata. Views are removed when the server stops.
- 2026-07-09: Added concurrent Dagster source-job orchestration, one shared lifecycle, failure propagation, post-server dedupe, cleanup, and SQLMesh-after-success ordering.
- 2026-07-09: Review found cleanup, actual-interval, partial-startup, failure-attribution, schedule, inspection, and documentation gaps; all were repaired with regression tests.
- 2026-07-09: Two consecutive `task verify` runs passed with all six sources, all 15 actual ingest-session overlap pairs, stable core row counts, zero persistent `main._dlt*`, and successful SQLMesh restatement.
- 2026-07-09: Focused suite passed 29 tests. Full `task ci` passed 153 tests with 80.37% coverage.

## Evidence and review

- `.10x/evidence/2026-07-09-parallel-quack-local-refresh.md`
- `.10x/reviews/2026-07-09-parallel-quack-local-refresh-review.md`

## Blockers

None.
