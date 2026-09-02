Status: done
Created: 2026-09-02
Updated: 2026-09-02
Parent: None
Depends-On: None

# Make USFWS a Dagster-owned manual workflow

## Scope

Implement `.10x/specs/usfws-manual-media-discovery.md`: expose an unscheduled manual Dagster job that derives validated targets from the modeled local public catalog, executes the existing Polaris Iceberg ingestion, and materializes truthful USFWS business/load-status lineage.

## Acceptance criteria

- A manual `usfws_ingest` job exists and has no schedule or shared-refresh membership.
- Targets come only from the configured modeled public relation and retain every existing fail-closed check.
- Search runs, image records, and `_dlt_load_status` have connected Dagster asset lineage and useful current-run metadata.
- Current-run verification prevents historical rows from masking failure.
- Existing licensing, approval, and publication behavior is unchanged.
- Missing/invalid targets fail before provider contact.
- Focused source, orchestration, registry, and lineage tests pass.

## Explicit exclusions

- Routine or scheduled USFWS ingestion.
- Implicit target lists.
- Automated image approval/publication.
- Changes to provider or media-safety semantics.

## References

- `.10x/specs/usfws-manual-media-discovery.md`
- `.10x/evidence/2026-09-02-usfws-polaris-iceberg-migration.md`
- `.10x/tickets/done/2026-09-02-migrate-usfws-to-polaris-iceberg.md`
- `packages/databox/databox/public_media_ingest.py`
- `packages/databox/databox/orchestration/domains/usfws.py`

## Evidence expectations

Record resolved asset dependencies, manual job composition, fail-before-contact tests, current-run checks, absence from schedules/shared refresh, focused verification, and residual risks.

## Progress and notes

- 2026-09-02: User ratified Dagster ownership as a manual dependency-driven media discovery workflow while preserving modeled target authority and all safety boundaries.
- 2026-09-02: Added the unscheduled `usfws_ingest` job and a three-output Dagster multi-asset connected to the modeled public target catalog. The asset reuses `ingest_public_usfws_media`, exposes current run/target/record metadata, remains excluded from shared refresh, and leaves licensing/publication unchanged. Updated the explicit-target registry contract and tests. Focused USFWS/orchestration/registry/refresh verification passed (36 tests); Ruff, format, and `git diff --check` passed.
- 2026-09-02: Corrected active operator documentation to name the Polaris Iceberg path and manual unscheduled Dagster job. Closure review passed; parent rerun included 39 focused tests plus Ruff, format, and diff checks. Evidence: `.10x/evidence/2026-09-02-load-status-lineage-and-manual-usfws.md`; review: `.10x/reviews/2026-09-02-load-status-refresh-usfws-closure-review.md`. No unresolved follow-up remains.

## Blockers

None.
