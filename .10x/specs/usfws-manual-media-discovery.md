Status: active
Created: 2026-09-02
Updated: 2026-09-02

# USFWS manual media discovery

## Purpose and scope

This specification governs Dagster ownership of the occasional USFWS candidate-media discovery workflow used by Rufous. It replaces the prior caller-owned orchestration boundary without changing target semantics, provider queries, licensing rules, media approval, or publication behavior.

## Behavior

- USFWS MUST remain unscheduled and excluded from shared parallel refresh.
- Dagster MUST expose one manually launched USFWS ingest job.
- The job MUST derive targets only from the persisted modeled `rufous_public.gbif_eod_occurrence` relation in the configured local DuckDB database.
- The target relation MUST exist, be nonempty, remain within `USFWS_MAX_TARGET_SPECIES`, and include Rufous Hummingbird; otherwise the job MUST fail before provider contact.
- Dagster MUST NOT embed, infer, or default a species target list.
- The job MUST retain current exact target normalization, request bounds, full-snapshot completeness, current-run identity, Iceberg merge, dlt lineage, and `_dlt_load_status` behavior.
- The job MUST materialize the USFWS search-run, image-record, and load-status assets with run metadata.
- `rufous_public.usfws_commercial_image` MUST remain the fail-closed licensing, identity, URL, credit, and restricted-mark eligibility boundary.
- Human approval and immutable media publication MUST remain separate manual operations.

## Acceptance scenarios

### Valid manual run

Given a configured local database containing a valid modeled public species catalog, when an operator manually launches the USFWS ingest job, then Dagster derives exactly those targets, publishes the current run to Polaris Iceberg, materializes search-run/image-record/load-status assets, and records counts without scheduling another run.

### Missing or invalid targets

Given a missing, empty, oversized, malformed, or Rufous-free modeled catalog, when the job is launched, then it fails before USFWS provider contact and publishes no successful load status.

### Routine refresh

Given `task full-refresh` or a source schedule, when routine ingestion runs, then USFWS is not selected and no USFWS request occurs.

## Constraints

The local database path and image cap MAY be explicit Dagster run configuration. Defaults MAY use the configured local database path and existing bounded cap, but target species themselves MUST never be configured implicitly.

## Explicit exclusions

- Automatic USFWS schedules or sensors.
- Inclusion in shared parallel refresh.
- Automatic image approval, replacement, preparation, or publication.
- Changes to licensing, identity, URL, attribution, or restricted-mark semantics.
