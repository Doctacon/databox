Status: recorded
Created: 2026-09-02
Updated: 2026-09-02
Relates-To: .10x/tickets/done/2026-09-02-repair-primary-iceberg-refresh-path.md, .10x/specs/canonical-dlt-source-registry.md

# Primary Iceberg refresh-path evidence

## What was observed

The primary runner uses `load_dlt_iceberg.py`, performs Polaris/S3 preflight, runs registry-eligible Dagster source jobs concurrently, inspects authoritative Iceberg tables and `_dlt_load_status`, and invokes SQLMesh only after successful ingestion and inspection. Quack server, dedupe, cleanup, and local raw-table inspection are absent from this path.

## Procedure

Inspected the runner, Task targets, source-refresh API command, tests, active registry specification, README, runbook, commands, incremental-loading guide, configuration guide, and ADR set. Ran focused refresh/source-runner tests and the combined closure suite.

```text
Focused refresh tests: 24 passed
Combined refresh/workflow tests: 35 passed
Ruff: passed
git diff --check: passed
```

## What this supports

This supports every ticket acceptance criterion, including concurrency, source-attributed failure behavior, authoritative inspection, SQLMesh-after-success, and operator documentation.

## Limits

No destructive full live multi-source refresh was run for closure. Prior individual source migrations established live Polaris/S3 writes; focused tests establish orchestration and failure sequencing.
