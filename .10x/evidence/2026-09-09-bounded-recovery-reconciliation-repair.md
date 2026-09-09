Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md, .10x/tickets/2026-09-04-verify-disaster-recovery-automation.md

# Bounded recovery reconciliation repair

## Authorization and scope

The user authorized only reconciliation findings 1 and 3 plus ticket/record closure bookkeeping. Snapshot-divergence validation was explicitly excluded and remains an unsupported blocker. No Docker, AWS, live restore, cleanup, source/model semantic, or unrelated-file operation ran.

## Changes

- Added source-named hermetic tests for an absent base backup and a missing required WAL segment. Both drive the real restore execution seam through a new owned target, simulate pgBackRest failure, and assert the target is preserved, the active volume is never mounted, no volume is deleted, and repository secrets are redacted.
- Updated `docs/runbook.md` to use reviewed corrected contract revision `e27990e`, distinguish that validation contract from the historical recovery-point revision, and document canonical failures versus explicit outside-registry warnings.
- Clarified final live-pass evidence with historical revision `e95b333092483a7103df9cfcfb39b8124fb7ed82`, validation-contract revision `e27990e9a87582db4d467b3fe2adab13bae0319c`, and the exact invariants remeasured by the final command versus inherited from prior evidence.
- Reconciled the live rollout ticket against reviewed plan/apply/operator/backup evidence. Every acceptance criterion was supported, so it closed without new live work.

## Validation

- `uv run pytest --no-cov -q tests/platform/test_catalog_recovery.py` — 34 passed.
- `uv run ruff check tests/platform/test_catalog_recovery.py` — passed.
- `uv run ruff format --check tests/platform/test_catalog_recovery.py` — passed.
- `uv run mypy tests/platform/test_catalog_recovery.py` — passed.
- `uv run python scripts/platform/check_secrets.py tests/platform/test_catalog_recovery.py docs/runbook.md .10x/evidence/2026-09-09-final-restored-catalog-validation-pass.md` — passed for three eligible files.
- `uv run mkdocs build --strict` — passed.
- `git diff --check` — passed.

## Remaining blocker

The isolated-recovery and aggregate verification tickets remain open. The validator does not compare the current snapshot embedded in the Polaris REST response with the current snapshot loaded from S3 `metadata-location`. This was not implemented, waived, superseded, or tested around. The timed drill remains blocked despite its recorded authorization.
