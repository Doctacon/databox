Status: done
Created: 2026-07-08
Updated: 2026-07-08
Parent: .10x/tickets/done/2026-07-08-build-birding-trip-copilot.md
Depends-On: None

# Add Xeno-canto source pipeline

## Scope

Add a first Xeno-canto dlt source integration for bird-call/media metadata used by the Birding Trip Copilot.

In scope:

- Add a `xeno_canto` source package under `packages/databox-sources/databox_sources/xeno_canto/`.
- Add Dagster source-domain wiring for a hermetic dlt ingest job/asset.
- Add source config and raw table declarations.
- Preserve recording IDs/URLs, species names/codes where available, quality/rating fields, date/location fields, license/attribution fields, and provenance fields.
- Treat audio as linked external media; ingest metadata only.
- Add tests for parsing/source behavior and source-layout validation.

Out of scope:

- Downloading or storing audio files.
- SQLMesh planner/media models.
- Agent tool implementation.
- Dive implementation.

## Acceptance criteria

- `xeno_canto` appears as a source in Databox source configuration and Dagster definitions.
- Local Quack-backed dlt ingestion can create physical `raw_xeno_canto` tables.
- The integration preserves license/attribution/provenance fields available from the upstream response.
- The implementation includes unit tests for response parsing and config/source behavior.
- `python scripts/check_source_layout.py` passes.
- Relevant targeted pytest tests pass.

## Evidence expectations

Record evidence with:

- commands run,
- raw table names created,
- representative row counts or empty-state explanation,
- tests executed,
- any API/license limitations discovered.

## Progress and notes

- 2026-07-08: Ticket opened from parent Birding Trip Copilot plan.
- 2026-07-08: Added Xeno-canto API v3 metadata-only dlt source, source config, Dagster ingestion domain, source registry entry, Quack dedupe key, Taskfile job wiring, `.env.example` key documentation, and operational platform-health SQL/Soda contract updates.
- 2026-07-08: Added unit tests covering recording flattening, authenticated endpoint call shape, missing API-key behavior, and config loading.
- 2026-07-08: Verified focused tests, source layout, platform-health codegen, affected-file ruff/format, Dagster definitions, targeted mypy, and mocked Quack-backed dlt smoke. See `.10x/evidence/2026-07-08-xeno-canto-source-pipeline.md`.

## Blockers

None.
