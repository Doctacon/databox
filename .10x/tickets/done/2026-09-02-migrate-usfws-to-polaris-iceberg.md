Status: done
Created: 2026-09-02
Updated: 2026-09-02
Parent: None
Depends-On: None

# Migrate explicit-target USFWS ingestion to Polaris Iceberg

## Scope

Move `raw_usfws.image_search_runs` and `raw_usfws.image_records` from Quack/DuckDB to the shared dlt-managed Polaris Iceberg destination while preserving caller-owned target derivation, bounded media retrieval, licensing/safety fields, and the absence of an unconfigured Dagster job. Update the direct SQLMesh consumer, explicit ingest verification, load-status publication, and source registry authority.

## Acceptance criteria

- USFWS remains explicit-target-only, unscheduled, and exposes no default Dagster asset/job.
- Targets remain derived and validated from the caller-provided modeled public database.
- Both dlt resources use Iceberg tables and retain their existing primary keys, merge semantics, fields, and `_dlt_*` lineage.
- Explicit ingestion writes to Polaris `raw_usfws`, publishes `_dlt_load_status`, and verifies completed runs/records from Polaris rather than local raw tables.
- `rufous_public.usfws_commercial_image` and its SQLMesh fixtures read `polaris_aws.raw_usfws` without weakening media eligibility, licensing, attribution, or restricted-mark rules.
- USFWS is marked Iceberg-authoritative and generated platform health includes it.
- Focused tests, SQLMesh tests, generator drift, pre-commit, and diff checks pass.

## Explicit exclusions

- Creating an implicit target list, default Dagster ingestion job, or schedule.
- Changing public-media selection, licensing, attribution, URL, or restricted-mark semantics.
- Migrating non-USFWS public-media providers.

## References

- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/specs/registry-derived-source-verification.md`
- `.10x/knowledge/dlt-polaris-iceberg-source-cutover.md`
- `.10x/tickets/done/2026-08-31-reconcile-usfws-source-contract-checker.md`

## Evidence expectations

Record focused source/orchestration tests, Iceberg table schema/lineage checks from a bounded explicit target, SQLMesh consumer verification, platform-health generation, pre-commit, and diff checks.

## Progress and notes

- 2026-09-02: User explicitly authorized the USFWS cutover. Existing source and records establish the explicit-target and media-safety contracts; no product semantics are changed.
- 2026-09-02: Migrated both resources and the explicit ingest runner to dlt-managed Polaris Iceberg, added load-status publication and Polaris verification, updated SQLMesh/fixtures, and marked USFWS Iceberg-authoritative without adding a Dagster job or schedule.
- 2026-09-02: The cap-one live attempt failed closed because the single Rufous target had 26 search results, proving incomplete snapshots remain rejected. A temporary caller-owned database with exactly the validated Rufous target and cap 50 then succeeded: one completed run, 40 raw records, dlt lineage on both tables, one load-status row, 25 eligible commercial-image rows, and platform health `success` with 41 committed rows.
- 2026-09-02: Focused tests passed (45), all SQLMesh tests passed (18), platform-health generation matched, pre-commit passed, and `git diff --check` passed.
- 2026-09-02: Closure review found aggregate historical rows could mask an empty current ingestion. The caller now supplies a generated run ID, and Polaris verification filters both tables to that run, requires exactly one complete run, matches both target counts to the submitted target set, matches persisted `record_count` to current-run image rows, and still requires at least one current-run record. Added a regression proving historical aggregates cannot mask an empty current run.

- 2026-09-02: Final adversarial closure review passed after current-run verification and the historical-masking regression were strengthened. Retrospective learning is preserved in the focused regression and migration evidence; no additional follow-up remains.

## Blockers

None.
