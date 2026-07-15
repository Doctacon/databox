Status: recorded
Created: 2026-07-14
Updated: 2026-07-14
Relates-To: .10x/tickets/done/2026-07-12-consolidate-canonical-dlt-source-registry.md, .10x/specs/canonical-dlt-source-registry.md

# Canonical dlt source registry consolidation evidence

## What was observed

The Python `SOURCES` registry now owns seven source identities, deterministic domain-module paths, current cadence/refresh flags, and verification profiles. Six sources use `http`; AVONET uses `file_snapshot` and remains unscheduled/outside shared refresh.

All seven Dagster domains use exactly one `_build_source()` for definition-time and execution-time construction. `definitions.py` imports source domains from registry-derived module paths and derives source assets, checks, jobs, and schedules without a manual source list. The resolved inventory retained seven ingest jobs, six daily jobs/schedules, the parallel refresh job/schedule, and the same six parallel-refresh sources.

The unused generic `PipelineConfig`, `PipelineSource`, auto-registry, Psycopg quality engine, six generic YAML configs, wrapper classes/factories, and generic config/database scaffold templates were removed. AVONET's pinned manifest SHA-256 remained `2995f2e8a37caa7ca2014bdc1acbd75d2b8a7a7067c89a380a8c910a3ad3bf97` before and after.

The scaffold now supports only the ratified `rest`/`http` and `file`/`file_snapshot` profiles, adds only the canonical registry entry, and does not edit Dagster Definitions. The unratified database profile was removed from the supported generator surface.

## Procedure and results

- `ruff format` over changed Python sources/tests: 8 files reformatted.
- `ruff check` over changed Python sources/tests: passed.
- Focused pytest after parent review repair: 67 passed across source registry, scaffold/layout/composition, parallel refresh, AVONET orchestration, settings, Quack destinations, and offline mock-backed GBIF/Xeno-canto resource tests.
- `python scripts/check_source_layout.py`: correctly returned exit 1 with 3 complete profiles and 4 incomplete profiles. Missing artifacts are AVONET schema/smoke; GBIF schema/smoke/idempotency; all four USGS Earthquakes files; and Xeno-canto schema/smoke/idempotency. These are owned by the dependent source-suite ticket, not hidden by layout validation.
- `dg check defs --use-active-venv`: all definitions loaded successfully.
- Focused MyPy across canonical registry, orchestration, source package, and scaffold/layout scripts: success, 34 source files.
- `git diff --check`: passed.
- Active implementation scan for `PipelineConfig`, `PipelineSource`, `get_registry`, `create_pipeline`, `quality.engine`, and database scaffold paths under packages/scripts/docs/pyproject: zero matches.
- `git diff --cached --name-only`: empty; no files staged.

Resolved Dagster inventory:

- ingest jobs: AVONET, eBird, GBIF, NOAA, USGS, USGS Earthquakes, Xeno-canto;
- daily jobs/schedules: all except AVONET;
- aggregate: `parallel_quack_full_refresh` and its schedule;
- shared refresh eligibility: eBird, GBIF, Xeno-canto, NOAA, USGS, USGS Earthquakes.

## What this supports

This supports the ticket criteria for one canonical registry/domain contract, registry-derived Dagster composition (including safe empty scaffold assets), preserved source/schedule/parallel-refresh inventory, retirement of unused generic configuration, preserved AVONET integrity, and updated scaffold/layout enforcement. It does not claim that all profile suites are complete; the checker now rejects the four incomplete profiles for the dependent test-suite ticket to repair.

## Limits

No provider request, dlt run, source refresh, SQLMesh command, DuckDB connection, or warehouse/runtime mutation was performed. Definition loading validates static composition but not a live source materialization.

Repository inspection found existing registry `raw_tables` omit active eBird `taxonomy`/`region_stats` and NOAA `datasets`. Expanding them would change generated platform-health/refresh inspection behavior outside this ticket's exclusions. The bounded dependent owner is `.10x/tickets/done/2026-07-12-reconcile-canonical-raw-table-inventory.md`; aggregate verification now depends on it.
