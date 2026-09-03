Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: .10x/tickets/2026-09-03-extract-rufous-repository.md
Depends-On: .10x/tickets/done/2026-09-03-bootstrap-standalone-rufous.md

# Migrate Rufous models and backend

## Scope

Complete destination Python/SQLMesh ownership after bootstrap: rewrite `birding_agent` and `rufous_public` inputs to `rufous_inputs_v1`, create independent SQLMesh/Soda configuration, finish `RufousSettings`, separate writable application state, replace private Databox destination dependencies in USFWS/iNaturalist media ingestion, and make all copied Python tests collect and pass. Port the manual target-bearing USFWS workflow through the pinned public `databox_sources.usfws` interface. Remove source-refresh backend behavior rather than restoring cross-repository invocation.

## Acceptance criteria

- No unresolved `rufous.destinations*`, `DataboxSettings`, `source_refresh_api`, raw Polaris, or Databox working-database dependency remains.
- All product SQL reads only the v1 artifact or Rufous-owned state and its 18 moved SQLMesh tests pass independently.
- All copied Python tests collect and pass with credential-free defaults.
- USFWS remains manual, unscheduled, modeled-target, current-run verified, and fail-closed.
- No private `databox.*` import or repository-relative Databox path exists.

## Explicit exclusions

- Web/deployment rewrite.
- Databox deletion.
- Production enablement.

## Evidence expectations

Record dependency rewrites, SQL relation mapping, settings contract, test collection and aggregate output, coupling scans, and review.

## Progress and notes

- 2026-09-03: Rewrote all product model inputs to the read-only `databox_product.rufous_inputs_v1` contract, retaining original raw-source strings only as provenance values. Added independent SQLMesh/Soda configuration, completed product/Polaris/SMTP settings with separate artifact/application paths, replaced private destination dependencies with Rufous-owned Iceberg and local dlt→DuckDB helpers, moved the private iNaturalist source, removed source-refresh backend coupling, and ported the manual unscheduled modeled-target USFWS Dagster job through the public `databox_sources.usfws` import.
- 2026-09-03: Supervisor clarified that 11/11 product-owned SQLMesh tests are the complete moved set; the other seven remain Databox-owned. In-scope Python aggregate passed (1,061), SQLMesh passed (11/11), Ruff/format/MyPy (53 files), secret scan (261 files), pre-commit, coupling scan, and diff check passed. The full destination run has exactly five failures, all unchanged `test_rufous_public_workflow.py` assertions durably owned by `.10x/tickets/2026-09-03-migrate-rufous-web-public-deployment.md`.
- 2026-09-03: Pushed the Databox boundary commit and replaced the local Git dependency with a portable GitHub SHA pin; `uv sync`, 1,061 in-scope tests, SQLMesh 11/11, Ruff, MyPy, and diff checks passed. Independent review found no in-scope issue. Evidence: `.10x/evidence/2026-09-03-rufous-models-and-backend-migration.md`; review: `.10x/reviews/2026-09-03-rufous-models-backend-review.md`.

## Blockers

None. Independent review passed. The five preserved public-workflow failures are explicitly excluded here and owned by `.10x/tickets/2026-09-03-migrate-rufous-web-public-deployment.md`.
