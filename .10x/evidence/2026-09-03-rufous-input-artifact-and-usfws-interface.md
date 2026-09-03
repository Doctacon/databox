Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Relates-To: .10x/tickets/done/2026-09-03-export-rufous-input-artifact.md, .10x/tickets/done/2026-09-03-publish-usfws-source-interface.md

# Rufous input artifact and USFWS interface evidence

## Implementation

`databox.product_artifact` defines the fixed twelve-relation v1 inventory, canonical contract digest, frozen ordered-schema digests, row bounds, public-safe observation predicate, atomic temporary-file replacement, strict read-only validation, and read-only consumer attachment. All source schema checks, counts, and row transfers execute inside one DuckDB transaction. Each query's zero-row materialized schema is validated before data transfer, preventing unreviewed `SELECT *` columns from entering v1. Resolved source/output equality fails before the CLI opens either database.

Nonempty raw snapshots record a deterministic `provenance-sha256:` identifier from sorted `_dlt_load_id`/`run_id` identities. Empty raw relations and modeled relations have an explicit null snapshot policy. Validation requires exact base-table and schema inventories, rejects views, validates all contract metadata, validates every relation metadata field, row bound/count, schema hash, privacy class, and snapshot policy.

`databox_sources.usfws` exports only `usfws_source`, `USFWS_MAX_TARGET_SPECIES`, and `UsfwsTarget`. Its isolated public-interface test now uses a genuinely recorded and sanitized bounded USFWS cassette for Berylline Hummingbird, blocks network during playback, and runs the public source through dlt. The protected fixture manifest includes the cassette.

## Automated verification

- Focused artifact/USFWS/registry/VCR suites passed, including offline cassette playback and new equality, snapshot-policy, unexpected-view, and incomplete-metadata cases.
- `task ci`: Ruff, format, MyPy (142 files), 1,514 pytest tests at 84.72% coverage, seven snapshots, secret scan (1,095 files), staging drift, and platform-health drift all passed.
- SQLMesh: 18/18 tests passed.
- Strict documentation build passed.
- Pre-commit all-files, `git diff --check`, and no-staged-files checks passed.

- Final adversarial repair added exact metadata-table schema validation and verifies each required provenance SHA-256 against recomputed relation content. A new adversarial test rejects both snapshot tampering and extra metadata columns; the six artifact tests, Ruff, formatting, targeted MyPy, and diff check passed after this repair.

## Limits

Artifact distribution remains local-file-only. Frozen v1 schemas intentionally fail closed on producer evolution. The source transaction establishes one coherent read boundary through the single DuckDB connection; independently bypassing Databox orchestration to mutate upstream external storage remains outside the local operator contract.
