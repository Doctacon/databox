Status: recorded
Created: 2026-09-02
Updated: 2026-09-02
Relates-To: .10x/tickets/2026-09-02-migrate-usfws-to-polaris-iceberg.md, .10x/specs/canonical-dlt-source-registry.md

# USFWS Polaris Iceberg migration evidence

## What was observed

USFWS remained explicit-target-only, unscheduled, and without a default Dagster asset or job. A live attempt using one validated Rufous Hummingbird target and `max_images_per_target=1` failed closed because the search returned 26 images, which exceeded the full-snapshot cap.

A second bounded run used a temporary caller-owned DuckDB containing exactly the validated Rufous target and a cap of 50. It completed with:

```text
target_species=1
raw_usfws.image_search_runs=1
raw_usfws.image_records=40
raw_usfws._dlt_load_status=1
rufous_public.usfws_commercial_image=25
analytics.platform_health=('success', 41)
```

Both business tables contained `_dlt_load_id` and `_dlt_id`.

## Procedure

1. Constructed a temporary local target database with the modeled public relation and exactly one validated `Selasphorus rufus` target.
2. Invoked `ingest_public_usfws_media` first with cap 1 to verify incomplete-snapshot rejection, then with cap 50.
3. Loaded the three Polaris tables through PyIceberg and inspected row counts and lineage fields.
4. Refreshed `rufous_public.usfws_commercial_image` and `analytics.platform_health` through targeted SQLMesh plans.
5. Ran focused source/orchestration/load-status tests, all SQLMesh tests, platform-health generation, pre-commit, and whitespace checks.

Observed verification results:

```text
Focused pytest: 45 passed
SQLMesh tests: 18 passed
Platform-health codegen: matched
Pre-commit: passed
git diff --check: passed
```

## Current-run verification repair

A closure review found that aggregate historical rows could mask an ineffective current ingestion. The runner now generates and supplies the source `run_id`, filters both Iceberg tables to that identity, and requires exactly one complete run with exact target completion, matching persisted record count, and at least one current-run record. A focused regression supplies nonempty historical records and a historical complete run, asserts both scans use `EqualTo("run_id", "current")`, and confirms that zero current-run records still fail closed. The focused suite passed four tests after this repair; Ruff and `git diff --check` passed.

## What this supports

This supports explicit caller-owned target derivation, preserved fail-closed snapshot behavior, successful dlt-managed Iceberg merge publication, lineage, load-status observability, and unchanged commercial-media filtering.

## Limits

The live observation covers one bounded Rufous target, not every possible target species or upstream response shape. It does not prove provider uptime. The temporary target database was removed, and no credentials or media bytes are retained in this record.
