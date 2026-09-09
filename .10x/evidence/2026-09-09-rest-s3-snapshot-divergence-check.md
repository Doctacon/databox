Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/done/2026-09-04-build-isolated-catalog-recovery-drill.md

# REST versus S3 snapshot divergence check

## Implementation

The restored-catalog validator now extracts `metadata.current-snapshot-id` from each Polaris load-table response and compares it with `StaticTable.current_snapshot().snapshot_id` loaded independently from the returned S3 `metadata-location`. Missing, malformed, or mismatched REST snapshot state produces only bounded per-table stage identifiers: `rest_snapshot_missing`, `rest_snapshot_malformed`, or `snapshot_divergent`.

The validator continues manifest planning and the limit-one data read after REST snapshot failure so one run preserves the existing object-read evidence while returning a nonzero aggregate. Credentials and third-party exception text remain excluded. No Docker, AWS, catalog, warehouse, or recovery operation ran.

## Validation

- `uv run pytest --no-cov -q tests/platform/test_catalog_recovery_validate.py` — 17 passed.
- Focused Ruff and format checks — passed.
- `MYPYPATH=packages/databox uv run mypy scripts/platform/catalog_recovery_validate.py` — passed.
- Focused secret scan and `git diff --check` — passed.

Focused tests cover matching, missing, malformed, and divergent snapshot IDs and verify bounded secret-free outcomes.

## Limits

Independent review and a separately authorized live rerun remain required. This compares current snapshot identity; it is not exhaustive warehouse-object integrity validation.
