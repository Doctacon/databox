Status: recorded
Created: 2026-07-14
Updated: 2026-07-14
Relates-To: .10x/tickets/done/2026-07-12-reconcile-canonical-raw-table-inventory.md, .10x/specs/canonical-dlt-source-registry.md

# Canonical raw-table inventory reconciliation evidence

## What was observed

The canonical registry previously listed four of six active eBird resources and two of three active NOAA resources:

- eBird before: `recent_observations`, `notable_observations`, `hotspots`, `species_list`
- NOAA before: `daily_weather`, `stations`

The active dlt source functions also expose eBird `taxonomy` and `region_stats`, and NOAA `datasets`. The registry now lists exactly those three existing omitted resources:

- eBird after: `recent_observations`, `notable_observations`, `hotspots`, `species_list`, `taxonomy`, `region_stats`
- NOAA after: `daily_weather`, `stations`, `datasets`

No other source inventory changed. `analytics.platform_health` was regenerated from the canonical registry and now includes the three corresponding `_dlt_load_id` row-count branches. `inspect_refresh_state` required no implementation change because it already iterates `Source.raw_tables`; a focused temporary-DuckDB test now proves it inspects all nine eBird/NOAA tables in registry order.

## Procedure and results

### Regeneration

Command:

`./.venv/bin/python scripts/generate_platform_health.py`

Result: wrote `transforms/main/models/analytics/platform_health.sql`. The generated diff adds only:

- `raw_ebird.taxonomy`
- `raw_ebird.region_stats`
- `raw_noaa.datasets`

### Focused tests

Command:

`./.venv/bin/pytest --no-cov -q tests/test_source_registry.py tests/test_parallel_refresh.py tests/test_avonet_orchestration.py`

Result: 35 passed. Coverage includes exact eBird/NOAA registry inventories, refresh inspection of all added existing tables in a pytest temporary DuckDB, registry/domain invariants, generated platform-health AVONET exclusion, and parallel-refresh behavior.

### Codegen and static checks

Commands and results:

- `./.venv/bin/python scripts/generate_platform_health.py --check` — passed; generated SQL matches the registry.
- `./.venv/bin/ruff check packages/databox/databox/config/sources.py tests/test_source_registry.py tests/test_parallel_refresh.py` — passed.
- `./.venv/bin/ruff format --check packages/databox/databox/config/sources.py tests/test_source_registry.py tests/test_parallel_refresh.py` — passed; three files already formatted.
- `./.venv/bin/mypy packages/databox/databox/config/sources.py packages/databox/databox/orchestration/parallel_refresh.py packages/databox/databox/quality/platform_health_codegen.py` — passed; no issues in three source files.
- `git diff --check` — passed.
- `git diff --cached --name-only` — empty; no files staged.

## What this supports

This supports that the canonical source inventory is complete for the three named source-observed omissions, generated platform-health SQL is registry-coherent, and refresh inspection now expects those existing raw tables without source/provider/write-disposition changes.

## Limits

No provider request, dlt source run, shared source refresh, SQLMesh command/apply, or connection to `data/databox.duckdb` occurred. The focused refresh inspection test created only a pytest temporary DuckDB and removed it through normal test cleanup. This evidence does not prove the three tables exist in every historical local warehouse; routine refresh behavior itself was intentionally not executed.
