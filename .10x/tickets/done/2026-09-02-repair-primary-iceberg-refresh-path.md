Status: done
Created: 2026-09-02
Updated: 2026-09-02
Parent: None
Depends-On: None

# Repair primary Iceberg refresh path

## Scope

Align `task full-refresh` and `task verify` with the now-authoritative dlt-managed Polaris Iceberg source path. Remove obsolete Quack-server ownership and local raw-table inspection from the primary refresh runner while retaining registry-derived source selection, bounded parallel execution, failure aggregation, and post-ingestion SQLMesh transformation.

## Acceptance criteria

- Primary refresh does not start or require Quack for raw ingestion.
- Refresh validates required Polaris/AWS configuration before source execution.
- Registry-derived runnable sources retain parallel execution and failure reporting.
- Post-ingestion inspection reads authoritative Polaris Iceberg tables/load status rather than local raw DuckDB tables.
- SQLMesh runs only after required source ingestion succeeds.
- `task full-refresh` and `task verify` descriptions and commands name the Iceberg path.
- Focused refresh tests, source checks, formatting, and diff checks pass.

## Explicit exclusions

- Repairing the Rufous public-release GitHub workflow.
- Changing source schedules, source semantics, or SQLMesh model behavior.
- Removing Quack code still used outside the primary refresh path.

## References

- `.10x/knowledge/dlt-polaris-iceberg-source-cutover.md`
- `Taskfile.yaml`
- `scripts/sources/load_dlt_quack.py`
- `packages/databox/databox/orchestration/parallel_refresh.py`

## Evidence expectations

Record focused tests, static source verification, Task command inspection, pre-commit, and diff checks.

## Progress and notes

- 2026-09-02: User explicitly authorized this repair with a five-minute execution bound.
- 2026-09-02: Replaced the primary Quack refresh entrypoint with the Polaris Iceberg runner, removed Quack server/dedupe/cleanup lifecycle from parallel orchestration, added AWS/Polaris preflight and Iceberg table/load-status inspection, and updated the API source-refresh runner and focused tests.
- 2026-09-02: Focused refresh suites passed (24 tests); Ruff check/format and `git diff --check` passed. No files are staged.
- 2026-09-02: Updated `docs/runbook.md` and `docs/commands.md` to describe Polaris/AWS prerequisites, concurrent Iceberg ingestion, authoritative table/load-status inspection, SQLMesh failure sequencing, and direct AVONET Iceberg publication.
- 2026-09-02: Updated the README introduction, architecture diagram, and warehouse quickstart for dlt-managed S3 Iceberg, local Polaris/PostgreSQL, local DuckDB models, Compose startup/health, and the paused public production deployment.
- 2026-09-02: Removed the obsolete Quack timeline-file dependency. Source workers now report their subprocess interval directly, preserving process-overlap and failure attribution without requiring instrumentation that Iceberg jobs do not emit. Focused parallel-refresh tests passed (11); Ruff and diff checks passed.
- 2026-09-02: Changed all six shared-refresh source ingest jobs to select only dlt assets while preserving their scheduled pipelines' targeted SQLMesh refresh assets. Added a registry-derived regression that rejects SQLMesh assets in shared source jobs. Focused refresh/registry tests passed (30); Ruff and diff checks passed.
- 2026-09-02: Adversarial closure review confirmed authoritative inspection precedes one central SQLMesh invocation and found only an overstated runbook timing description; corrected it to worker subprocess overlap. Parent rerun included 39 focused tests plus Ruff, format, and diff checks. Evidence: `.10x/evidence/2026-09-02-load-status-lineage-and-manual-usfws.md`; review: `.10x/reviews/2026-09-02-load-status-refresh-usfws-closure-review.md`. No unresolved follow-up remains.

## Blockers

None.
