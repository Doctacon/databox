Status: done
Created: 2026-08-31
Updated: 2026-08-31
Parent: None
Depends-On: None

# Reconcile the USFWS source contract checker

## Scope

Reconcile the canonical source-layout checker with the intentional explicit-target-only USFWS domain. The current registry includes USFWS, while `packages/databox/databox/orchestration/domains/usfws.py` deliberately exports no unconfigured asset or job. The checker nevertheless requires a callable `usfws_dlt_assets`, populated `assets`/`dlt_asset_keys`, and `ingest_job`.

Do not invent an implicit USFWS target set or expose an unsafe Dagster job. Ratify and implement the correct executable contract for registered explicit-target-only sources.

## Acceptance criteria

- Active source registry/specification and checker agree on whether an explicit-target-only registered source may omit an unconfigured Dagster asset/job.
- `uv run python scripts/sources/check_source_layout.py` and `uv run python scripts/sources/source_ci.py matrix --pretty` pass.
- Existing USFWS explicit-target safety and source-profile tests pass without live provider calls.

## Progress and notes

- 2026-08-31: Discovered during the behavior-preserving root test/script reorganization. The current checker and the pre-change `HEAD:scripts/check_source_layout.py` both fail with the same four USFWS errors, proving the failure predates that reorganization.
- 2026-08-31: Ratified `Source.orchestration_mode` in the active canonical registry specification with `default` and `explicit_targets` modes. Updated the active source inventory/verification records from seven to the current eight sources and documented USFWS as the explicit-target example.
- 2026-08-31: Declared USFWS `orchestration_mode="explicit_targets"`. Repaired the checker to require an explicit-target builder while rejecting an unconfigured dlt asset, non-empty assets/keys, an ingest job, scheduling, or parallel-refresh eligibility. No implicit target set or Dagster job was added.
- 2026-08-31: Added positive and adversarial checker/registry tests. Focused network-blocked verification passed 145 tests. Live checker passed 8/8 and the deterministic matrix contains all eight sources. Complete network-blocked Python verification passed 1,504 tests and seven snapshots at 85.00% coverage. Ruff, format, MyPy (140 files), strict MkDocs, and diff/no-stage gates passed. Evidence: `.10x/evidence/2026-08-31-usfws-explicit-target-source-contract.md`.
- 2026-08-31: Acceptance re-read is fully supported: registry/spec/checker agree, both required commands are green, and existing USFWS explicit-target safety/profile tests pass offline. Ticket closed.
- 2026-08-31: Follow-up review found two stale source-count phrases in active acceptance scenarios. Updated canonical existing-source wording from seven to eight entries and registry-derived future-source wording from an eighth to a ninth source, preserving the scenarios' meaning. Focused active-spec reference and consistency checks passed; evidence appended at `.10x/evidence/2026-08-31-usfws-explicit-target-source-contract.md`.

## Blockers

None.
