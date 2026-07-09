Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Parallel Quack Local Refresh

## Purpose and scope

This spec governs concurrent dlt source loading into the single local `data/databox.duckdb` warehouse through one shared Quack server.

## Required behavior

A full local refresh MUST:

1. start exactly one Quack server that owns `data/databox.duckdb`,
2. launch each registered dlt source as an independent hermetic client/job,
3. allow independent source loads to execute concurrently through the Quack protocol,
4. wait for all source loads to complete,
5. stop the Quack server cleanly,
6. perform any required source-scoped deduplication safely,
7. run native SQLMesh only after all required source loads succeed.

Independent source failures MUST be attributed to the failing source. The refresh MUST NOT report overall success or run SQLMesh if any required source load fails.

## State and schema isolation

- Each source MUST retain isolated dlt pipeline state and configuration.
- Each source MUST write physical tables and `_dlt_*` operational metadata under its own `raw_<source>` schema.
- Source clients MUST NOT create persistent `main._dlt*` tables or views.
- Temporary compatibility state MUST NOT be globally source-specific in a way that concurrent clients can overwrite.
- Source-specific post-load deduplication MUST NOT mutate another source's raw tables.
- Client database files and temporary state MUST be cleaned after the refresh without deleting `.env`, `.venv/`, `data/databox.duckdb`, `.dagster/`, or `.logs/`.

## Concurrency contract

Parallel means at least two independent registered source clients are observed in overlapping load intervals against the one server. Merely launching sequential subprocesses from a shared command does not satisfy this requirement.

Concurrency SHOULD be bounded to the registered source count and MAY use a lower configured maximum only if the default still executes more than one source concurrently.

There is no sequential fallback in the product contract. If current Quack/dlt behavior cannot safely support this, the implementation ticket MUST record reproducible evidence and remain blocked rather than silently reverting to sequential loads.

## Dagster contract

Dagster remains the orchestration/UI surface. Each source remains independently materializable as a source job/asset, while the full-refresh orchestration composes those source loads against the shared server lifecycle.

The implementation MUST NOT represent physical `_dlt_*` tables as Dagster assets.

## Verification

Tests/evidence MUST prove:

- one server start and stop,
- overlapping source-client execution,
- successful writes into at least two distinct `raw_<source>` schemas,
- repeat-run state restore/idempotency behavior,
- no persistent `main._dlt*` relations,
- failure propagation and cleanup,
- existing source jobs remain independently runnable.

## Acceptance criteria

- `task full-refresh` and smoke verification use one shared Quack server and concurrent hermetic source clients.
- All registered source data lands in the single local DuckDB.
- SQLMesh runs only after successful source completion.
- Required concurrency, state isolation, cleanup, and failure semantics are covered by tests and recorded evidence.
