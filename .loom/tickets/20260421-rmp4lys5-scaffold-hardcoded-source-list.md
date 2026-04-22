---
id: ticket:scaffold-hardcoded-source-list
kind: ticket
status: ready
created_at: 2026-04-21T21:00:00Z
updated_at: 2026-04-21T21:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 5
depends_on: []
---

# Goal

Make the "dataset-agnostic platform" claim in the README honest. Every hardcoded `("ebird", "noaa", "usgs")` tuple or per-source `if backend == motherduck` dict entry must derive from a single registry, so `new_source.py` can wire a new source end-to-end with zero edits to shared infrastructure files.

# Why

The 4th source (`usgs_earthquakes`) exposed the scaffold seams:

1. `scripts/smoke.py` imports only `ebird_dlt_assets`, `noaa_dlt_assets`, `usgs_dlt_assets`. The smoke run is silent on earthquakes — green smoke is a lie for that source.
2. `packages/databox/databox/orchestration/_factories.py::_source_for_key` hardcodes `for src in ("ebird", "noaa", "usgs")`. Earthquakes asset keys never match, so `FRESHNESS_BY_SOURCE[src]` never fires on earthquake marts. The 24-hour freshness policy claim in the README is quietly violated for earthquakes.
3. Same file's `FRESHNESS_BY_SOURCE` map has three hardcoded entries. Adding a 5th source = edit-site.
4. `packages/databox/databox/config/settings.py` requires a new `Field` + new `@property` + new key in `sqlmesh_config()`'s local/motherduck catalog dicts for every source. Four edit sites.
5. `transforms/main/models/analytics/platform_health.sql` UNIONs three sources explicitly. Earthquakes silently missing from observability.
6. The `DataboxSQLMeshTranslator.get_asset_key_name` decides "raw catalog" via a `startswith("raw_")` substring match — convention masquerading as logic.

Staff-level review reads each of these in under a minute.

# In Scope

- Introduce a single source-registry (either extend `packages/databox-sources/databox_sources/registry.py` or create `packages/databox/databox/config/sources.py`) that lists every active source with: `name`, `raw_catalog`, `freshness_policy`, `dlt_assets_import_path`, `sqlmesh_asset_keys_import_path`, `has_analytics_membership`.
- Refactor `_factories.py`:
  - `_source_for_key` iterates the registry, not a hardcoded tuple
  - `FRESHNESS_BY_SOURCE` is derived from the registry
  - `apply_freshness` still works unchanged at call site
- Refactor `settings.py`:
  - `raw_<source>_path` properties derive from registry (or are replaced by a single `raw_catalog_path(source)` method)
  - `sqlmesh_config()`'s catalog dicts build via a comprehension over the registry
  - `motherduck_database_names` already partially derives — finish the job so it's registry-driven, not dir-introspected
- Refactor `scripts/smoke.py` to iterate over the registry's dlt-asset entries
- Refactor `transforms/main/models/analytics/platform_health.sql` to be generated (jinja / macro) from the registry, or split into a view-per-source + an umbrella UNION ALL that's codegenned alongside staging SQL
- `scripts/new_source.py` auto-appends the new source to the registry (if it doesn't already)
- Replace the `.startswith("raw_")` heuristic in `DataboxSQLMeshTranslator` with a registry lookup

# Out of Scope

- Refactoring the `domains/*.py` files to a single parameterized factory (keep the per-domain files — they're the right place for source-specific knobs like asset-limit overrides)
- Making the registry runtime-mutable (a Python module with a list of dataclass entries is enough)
- A new `add-source` Dagster resource or anything that treats sources as first-class runtime objects

# Acceptance Criteria

- Deleting any source from the registry causes `definitions.py` + `scripts/smoke.py` + `_factories.py` + `platform_health.sql`-equivalent to cleanly omit that source with zero further edits
- Adding a new source via `python scripts/new_source.py foo` + running `task install` yields a runnable Dagster stack that schedules, materializes, checks freshness, and appears in `platform_health` — no manual edits to any shared file outside the registry
- `scripts/smoke.py` runs the new source and the existing four
- A new test `tests/test_source_registry.py` asserts: every domain module's `dlt_asset_keys` + `sqlmesh_asset_keys` + schedule correspond to a registry entry (and vice versa)
- `grep -rn "ebird\|noaa\|usgs" packages/databox/databox/orchestration/_factories.py` returns zero matches outside tests and docstrings

# Approach Notes

- The registry should be a plain Python module with a `dataclasses.dataclass` per source and a module-level `SOURCES: list[Source]`. No config files, no YAML — the thing that imports domain modules is Python; let it stay Python.
- Sequence: land the registry first with the existing four sources encoded, wire one consumer at a time (`_factories._source_for_key` is the safest first switch because it's pure), verify `task ci` green between each hop.
- Watch for circular imports: the registry cannot import domain modules, but domain modules can import the registry. Keep the direction strict.

# Evidence Expectations

- Commit series (or single squashed commit) refactoring each consumer
- `task ci` green before and after each hop (or one CI run at the end if squashed)
- A demonstration diff: `scripts/new_source.py` run on a throwaway name adds exactly one registry entry and zero edits elsewhere
