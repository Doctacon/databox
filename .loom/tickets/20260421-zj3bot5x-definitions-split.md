---
id: ticket:definitions-split
kind: ticket
status: ready
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 1
depends_on:
  - ticket:collapse-packages
---

# Goal

Break the 469-line `databox.orchestration.definitions` module into per-domain files under `databox/orchestration/domains/`, assembled by a thin root `definitions.py` that globs the domain modules.

# Why

A single 469-line file holding every Dagster asset, asset check, schedule, and sensor across three sources scales badly. At 20 sources it would be 3000+ lines and every source edit would touch the same file — merge-conflict magnet, diff-review pain, and no clear way for `scripts/new_source.py` to mechanically add wiring.

Per-domain files mirror the per-source layout convention (ticket:source-layout-convention) and let the generator drop a single new file rather than surgically edit a giant one. Freshness SLAs (ticket:freshness-slas) declare naturally per domain.

# In Scope

- Create `packages/databox/databox/orchestration/domains/` directory
- One module per source domain:
  - `domains/ebird.py` — all ebird assets, asset checks, schedules, sensors
  - `domains/noaa.py` — NOAA equivalents
  - `domains/usgs.py` — USGS equivalents
  - `domains/analytics.py` — cross-domain marts (flagship + platform_health + any shared analytics)
- Each domain module exports:
  - `assets: list[AssetsDefinition]`
  - `asset_checks: list[AssetChecksDefinition]`
  - `schedules: list[ScheduleDefinition]`
  - `sensors: list[SensorDefinition]`
  - `jobs: list[JobDefinition]` (if any)
- Root `definitions.py` becomes a thin loader that imports each domain module and flattens:
  ```python
  from databox.orchestration.domains import ebird, noaa, usgs, analytics
  defs = Definitions(
      assets=[*ebird.assets, *noaa.assets, *usgs.assets, *analytics.assets],
      ...
  )
  ```
- Shared helpers (dlt-pipeline asset factory, SQLMesh-model asset factory, Soda-check factory) move to `databox/orchestration/_factories.py`
- Keep root definitions ≤60 lines

# Out of Scope

- Automatic glob-and-discover at the root (explicit import list is clearer and mypy-friendly; generator adds an import line)
- Restructuring how SQLMesh assets are generated (keep the current factory pattern)
- Changing any schedule cadences

# Acceptance Criteria

- `wc -l packages/databox/databox/orchestration/definitions.py` ≤ 60
- Each `domains/*.py` is focused (no cross-source imports except via `_factories`)
- `uv run dagster definitions list -m databox.orchestration.definitions` shows exactly the same assets, checks, schedules, sensors, and jobs as before — diff-identical
- `task dagster:materialize -- analytics.fct_species_environment_daily` still runs
- Soda asset checks still fire as before
- All 30 existing tests pass
- mypy clean

# Approach Notes

- Order of extraction: analytics first (smallest), then ebird, noaa, usgs. Each extraction is an independent commit so bisect stays useful
- Preserve lineage annotations — move `deps=[...]` lists with the assets, not into `_factories`
- Keep `_factories.py` small; it should hold only repeated wiring patterns, not business logic

# Evidence Expectations

- `dagster definitions list` diff — identical before/after
- Line-count table in PR description: before (single file 469), after (≤60 root + ~100 each domain)
- Green CI
