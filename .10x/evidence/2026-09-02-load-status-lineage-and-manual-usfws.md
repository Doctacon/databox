Status: recorded
Created: 2026-09-02
Updated: 2026-09-02
Relates-To: .10x/tickets/done/2026-09-02-connect-load-status-lineage.md, .10x/tickets/done/2026-09-02-make-usfws-dagster-owned-manual-workflow.md, .10x/tickets/done/2026-09-02-repair-primary-iceberg-refresh-path.md

# Load-status lineage and manual USFWS evidence

## What was observed

All eight registry-managed `_dlt_load_status` dependencies of `sqlmesh/analytics/platform_health` resolve to declared materializable Dagster assets. Seven routine sources publish status through downstream ingestion assets after dlt completion; USFWS exposes a manual, unscheduled modeled-target job with search-run, image-record, and status outputs. Shared refresh excludes USFWS and runs SQLMesh once after worker success and authoritative Iceberg inspection.

## Procedure

- Inspected the resolved Dagster asset graph through registry-derived tests.
- Ran focused load-status, parallel-refresh, source-registry, USFWS orchestration, and public-media-ingest tests.
- Ran Ruff, formatting checks, and `git diff --check`.
- Adversarially reviewed graph composition, scheduling exclusions, current-run filtering, refresh sequencing, and active operator documentation.

## Results

The implementation pass reported 35 focused tests passing. Parent verification independently reran 24 USFWS/orchestration/registry tests successfully. Review confirmed all eight status parents are declared, USFWS current-run verification filters both Iceberg tables by generated run ID, and shared refresh sequences one central SQLMesh invocation after inspection. Review found two documentation inconsistencies; `docs/rufous-public-release.md` now names the manual unscheduled Dagster job and Polaris Iceberg path, and `docs/runbook.md` now describes worker subprocess rather than dlt-session overlap.

## What this supports

This supports the three tickets' static lineage, orchestration, safety, documentation, and focused-test acceptance criteria.

## Limits

No live provider refresh was run in this closure pass. Prior migration evidence records bounded live Iceberg verification. Static graph resolution and mocked focused tests do not prove future provider availability or credentials.
