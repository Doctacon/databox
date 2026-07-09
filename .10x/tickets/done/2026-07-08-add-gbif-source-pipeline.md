Status: done
Created: 2026-07-08
Updated: 2026-07-08
Parent: .10x/tickets/done/2026-07-08-build-birding-trip-copilot.md
Depends-On: None

# Add GBIF source pipeline

## Scope

Add a first GBIF dlt source integration for the Birding Trip Copilot.

The implementation MUST follow Databox source conventions in `docs/new-source.md` and `.10x/specs/birding-agent-data-integrations.md`.

In scope:

- Add a `gbif` source package under `packages/databox-sources/databox_sources/gbif/`.
- Add Dagster source-domain wiring for a hermetic dlt ingest job/asset.
- Add source config and raw table declarations.
- Preserve GBIF identifiers, names/taxonomy fields, occurrence dates, coordinates/region fields, basis/status fields, and provenance fields exposed by the selected endpoint.
- Use environment variables for credentials only if the selected endpoint requires them.
- Add tests for parsing/source behavior and source-layout validation.

Out of scope:

- SQLMesh CDM/planner modeling for GBIF-derived tables.
- Agent tool implementation.
- Dive implementation.
- Bulk-download workflows unless a first endpoint requires them and credentials/terms are explicitly handled.

## Acceptance criteria

- `gbif` appears as a source in Databox source configuration and Dagster definitions.
- Local Quack-backed dlt ingestion can create physical `raw_gbif` tables.
- dlt metadata tables remain physical raw-schema tables, consistent with existing Quack behavior.
- The implementation includes unit tests for response parsing and config/source behavior.
- `python scripts/check_source_layout.py` passes.
- Relevant targeted pytest tests pass.
- No secrets are written into `.10x`, docs, fixtures, or code.

## Evidence expectations

Record evidence with:

- commands run,
- raw table names created,
- representative row counts or empty-state explanation,
- tests executed,
- any endpoint/credential limitations discovered.

## Progress and notes

- 2026-07-08: Ticket opened from parent Birding Trip Copilot plan.
- 2026-07-08: Implemented `databox_sources.gbif` using the public GBIF occurrence search endpoint for bird (`classKey=212`) records in the configured geography. No GBIF credentials are required for this endpoint, so no secret names or values were added.
- 2026-07-08: Wired `gbif` into the Databox source registry, Dagster definitions, Quack dedupe keys, source-layout convention, `task full-refresh`/`task verify` source loops, MotherDuck database-name coverage, and generated operational `analytics.platform_health` coherence.
- 2026-07-08: Scope clarification from supervisor: updating generated operational `analytics.platform_health` SQL and Soda source valid-values is allowed as source wiring/operational health coherence; no planner/CDM SQLMesh models were added.
- 2026-07-08: Added GBIF unit tests for occurrence flattening, public endpoint resource calls, and config loading.
- 2026-07-08: Verified focused ruff, mypy, targeted pytest, source-layout lint, platform-health codegen check, Dagster definition load, temp Quack ingestion, and local `gbif_ingest` smoke success. Evidence: `.10x/evidence/2026-07-08-gbif-source-pipeline.md`.
- 2026-07-08: Final worker validation ran `task ci` successfully (`128 passed`) and re-inspected `raw_gbif.occurrences` plus raw dlt metadata base tables.

## Blockers

None.
