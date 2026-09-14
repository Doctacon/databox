Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/done/2026-09-09-reconcile-restored-catalog-registry-drift.md

# eBird normalized child-table registry declaration

## Authorized change

The user confirmed that `taxonomy__banding_codes`, `taxonomy__com_name_codes`, and `taxonomy__sci_name_codes` are canonical eBird physical raw tables retained for recovery/readability validation but intentionally not consumed by the current CDM. No SQLMesh transform, CDM field, USFWS/probe policy, or live service/catalog operation was authorized.

## Implementation

- Added exactly the three deterministic normalized child tables to the eBird `raw_tables` registry inventory.
- Added explicit `Source.normalized_child_tables` metadata containing exactly the three authorized eBird children. `Source.resource_tables` subtracts only this explicit subset, so `__` is never used as an ownership heuristic.
- Registry validation rejects duplicate/invalid normalized children, children absent from `raw_tables`, orphan parent prefixes, and any `__` raw table not explicitly declared as normalized. Source layout still compares actual dlt resources with the explicit `resource_tables` projection.
- Removed the three tables from the Species taxonomy concept and source DBML child-role annotations.
- Classified all three under taxonomy `_excluded` and DBML `excluded:` with the consistent reason: `dlt-normalized taxonomy code list retained raw for recovery but not used by the current CDM`.
- Removed the three excluded source tables and their code/list linkage fields from `ontology.ison` and `ontology.md`; the human-readable ontology lists them as exclusions. `CDM.dbml` and SQLMesh were unchanged because neither claimed or consumed these fields.
- Kept recovery validation registry-derived: it now expects 25 canonical tables (18 physical source tables plus seven `_dlt_load_status` tables) without a validator-owned table list.

No Docker, AWS, catalog, warehouse, source-refresh, recovery, or cleanup command ran.

## Validation

- Initial implementation validation: 147 focused tests passed.
- P1 repair validation: `uv run pytest --no-cov -q tests/sources/test_check_source_layout.py tests/sources/test_source_registry.py tests/sources/test_source_builders.py tests/sources/test_parallel_refresh.py tests/sources/test_quack_destinations.py tests/sources/test_source_modeling_contract.py tests/platform/test_catalog_recovery_validate.py` — 148 passed.
- `uv run python scripts/sources/check_source_layout.py` — seven sources OK, zero incomplete/failing/registry errors.
- `uv run python scripts/sources/check_source_modeling.py` — seven registered sources complete the modeling workflow.
- `uv run python scripts/analytics/generate_platform_health.py --check` — generated SQL matches the registry.
- Focused Ruff check and format check — passed.
- `uv run python -m json.tool .schema/environmental_observations/taxonomy.json` — passed.
- Focused repository secret scan — passed.
- `git diff --check` — passed.

## Limits

The initial review's P1 `__` ownership-heuristic finding was repaired with explicit child metadata and regression tests; follow-up independent review remains required. A live recovery-validation rerun was not authorized and did not run. The separate warning/failure policy for restored noncanonical USFWS and probe namespaces remains blocked in `.10x/tickets/done/2026-09-09-classify-noncanonical-restored-catalog-state.md`.
