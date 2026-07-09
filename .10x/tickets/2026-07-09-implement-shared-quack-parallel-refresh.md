Status: open
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/2026-07-09-build-local-birding-copilot-product.md
Depends-On: .10x/tickets/2026-07-09-decommission-motherduck-platform-support.md

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

None.

## Blockers

None known before execution; protocol validation is the first scoped step.
