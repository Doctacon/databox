---
id: ticket:sqlmesh-test-depth
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

Bring SQLMesh unit-test coverage from 5 tests against ~28 models up to a floor where every mart model has at least one test, and every non-trivial piece of business logic (window anomalies, H3 joins, cross-domain fact grain) has an explicit expected-output fixture.

# Why

`transforms/main/tests/test_models.yaml` contains five tests. The repo has ~28 SQLMesh models including the flagship `analytics.fct_species_environment_daily` with two windowed z-score computations and a cross-domain four-table join. Soda contracts check schema shape and null counts; they do not check whether the join math is right. A staff-level reviewer flipping to the tests file sees the gap in seconds: "the windowed anomaly is the flagship claim, there is no test that asserts the z-score for a three-day rainfall spike." The entire portfolio argument hinges on that mart being correct; the test coverage should reflect that.

# In Scope

- Add at least one SQLMesh unit test per mart model:
  - `ebird.fct_daily_bird_observations`
  - `ebird.fct_hotspot_species_diversity`
  - `ebird.dim_species`
  - `ebird.int_ebird_enriched_observations`
  - `ebird.int_observations_by_h3_day`
  - `noaa.fct_daily_weather`
  - `noaa.int_weather_by_h3_day`
  - `usgs.fct_daily_streamflow`
  - `usgs.int_streamflow_by_h3_day`
  - `usgs_earthquakes.fct_daily_earthquakes`
  - `analytics.fct_bird_weather_daily`
  - `analytics.fct_species_weather_preferences`
  - `analytics.fct_species_environment_daily`
  - `analytics.platform_health`
- Special-case coverage for the flagship mart:
  - A test with 8 days of synthetic precip values covering the 7-day window boundary, asserting the z-score output matches a hand-computed value for the 8th day
  - A test for the LEFT JOIN semantics: a bird observation with no weather / no streamflow still appears, with nulls in the weather/streamflow columns
  - A test for the `is_hot_day` and `is_rainy_day` flags at the boundary (`tmax_c = 30` → `is_hot_day = 1`; `prcp_mm = 0` → `is_rainy_day = FALSE`)
- Split `test_models.yaml` into one file per schema (`tests/ebird.yaml`, `tests/noaa.yaml`, etc.) — the single file is already at 182 lines and will triple

# Out of Scope

- Testing staging views (they are rename-only views; the staging-codegen gate already asserts shape)
- Property-based tests (SQLMesh's YAML format doesn't support them cleanly; skip)
- Integration tests against a real full DuckDB (those are the Dagster smoke run, not the SQLMesh test suite)

# Acceptance Criteria

- `sqlmesh test` from `transforms/main/` runs ≥20 tests, all green
- Every model listed in "In Scope" has a test file entry
- The flagship mart's three special-case tests exist and pass
- `task ci` includes `sqlmesh test` as a required step (verify it already does; if not, add)

# Approach Notes

- Use the existing `test_stg_ebird_observations` entry as a template
- The windowed z-score test requires `vars:` input with dates spanning the window — SQLMesh handles this natively via `inputs:` rows
- For H3 cell computations, use a known `(lat, lng)` → `h3_cell_to_lat/lng` round-trip; do not invent cell IDs
- Prefer minimal fixtures: 2-3 input rows per table, one expected output row per test, where possible

# Evidence Expectations

- `sqlmesh test` output showing N ≥ 20 tests passed
- Link to the PR that splits the YAML into per-schema files
