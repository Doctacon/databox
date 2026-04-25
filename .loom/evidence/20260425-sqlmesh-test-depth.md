---
id: evidence:sqlmesh-test-depth
kind: evidence
status: accepted
created_at: 2026-04-25T00:00:00Z
updated_at: 2026-04-25T00:00:00Z
scope:
  kind: workspace
links:
  ticket: ticket:sqlmesh-test-depth
---

# Summary

`sqlmesh test` from `transforms/main/` now runs **22 tests** (up from 5),
all green. Every mart and intermediate model listed in the ticket has at
least one test, and the flagship `analytics.fct_species_environment_daily`
has explicit special-case coverage for the windowed z-score, the LEFT-JOIN
behavior on missing weather/streamflow rows, and the `is_hot_day` /
`is_rainy_day` boundary conditions.

# Test inventory

```
test_ebird_staging.yaml          3 tests (existing — split out)
test_noaa_staging.yaml           2 tests (existing — split out)
test_ebird.yaml                  5 tests (new)
test_noaa.yaml                   2 tests (new)
test_usgs.yaml                   2 tests (new)
test_usgs_earthquakes.yaml       1 test  (new)
test_analytics.yaml              7 tests (new)
                                ──────────
Total                           22 tests
```

# Coverage map

Each ticket-scope model → test name:

| Model | Test |
|---|---|
| `ebird.dim_species` | `test_dim_species_picks_latest_loaded_taxonomy` |
| `ebird.int_ebird_enriched_observations` | `test_int_ebird_enriched_observations_joins_and_buckets` |
| `ebird.int_observations_by_h3_day` | `test_int_observations_by_h3_day_groups_and_counts` |
| `ebird.fct_daily_bird_observations` | `test_fct_daily_bird_observations_aggregates_per_region_date_species` |
| `ebird.fct_hotspot_species_diversity` | `test_fct_hotspot_species_diversity_shannon_index` |
| `noaa.fct_daily_weather` | `test_fct_daily_weather_pivots_datatypes_per_station_date` |
| `noaa.int_weather_by_h3_day` | `test_int_weather_by_h3_day_nearest_station_and_unit_conversion` |
| `usgs.fct_daily_streamflow` | `test_fct_daily_streamflow_pivots_parameters_and_converts_temp` |
| `usgs.int_streamflow_by_h3_day` | `test_int_streamflow_by_h3_day_nearest_gauge` |
| `usgs_earthquakes.fct_daily_earthquakes` | `test_fct_daily_earthquakes_aggregates_per_day` |
| `analytics.fct_bird_weather_daily` | `test_fct_bird_weather_daily_pivots_weather_and_joins_birds` |
| `analytics.fct_species_weather_preferences` | `test_fct_species_weather_preferences_aggregates_per_species` |
| `analytics.fct_species_environment_daily` | `test_fct_species_environment_daily_basic_columns` (+ 3 special-case below) |
| `analytics.platform_health` | `test_platform_health_picks_latest_per_source` |

Flagship special-case tests (per ticket):

- `test_fct_species_environment_daily_zscore_8day_window` — eight days of
  precip, hand-computed z-score against the 7-day rolling window
- `test_fct_species_environment_daily_left_join_missing_weather` —
  observation with no matching weather/streamflow row, asserts NULL columns
  and that `is_hot_day`/`is_rainy_day` evaluate FALSE on NULL inputs
- `test_fct_species_environment_daily_hot_rainy_boundary` — two days
  exercising `tmax_c=30 → is_hot_day=1` and `prcp_mm=0 → is_rainy_day=FALSE`
  versus `tmax_c=29.9 → 0` and `prcp_mm=0.1 → TRUE`

# Evidence

## `sqlmesh test` output

```
$ cd transforms/main && uv run sqlmesh test
......................**Successfully Ran `22` Tests Against `duckdb`**
```

## Lint + type

```
$ uv run ruff check .
All checks passed!

$ uv run mypy packages/
Success: no issues found in 50 source files
```

## Pytest

```
======================= 107 passed, 27 warnings in 2.86s =======================
```

# Implementation notes worth keeping

Three things bit during implementation that the next person touching this
should know:

1. **SQLMesh test files require the `test_` prefix.** The ticket suggests
   `tests/ebird.yaml`; the file actually has to be `tests/test_ebird.yaml`
   or the discovery silently picks up zero tests.
2. **H3 needs a `test_connection` declaration on every gateway.** SQLMesh's
   in-process test DuckDB does not inherit `extensions=[h3]` from the prod
   `connection`; it falls back to a bare `DuckDBConnectionConfig()` if the
   gateway's `test_connection` is unset. The fix is one shared
   `test_connection` instance on both `local` and `motherduck` gateways in
   `packages/databox/databox/config/settings.py`. Without this, every
   H3-using model's test fails with
   `Catalog Error: Scalar Function with name h3_latlng_to_cell_string does not exist`.
   Note: `connector_config={"allow_community_extensions": True}` does NOT
   work — DuckDB rejects that setting after the database is open. Once the
   extension is INSTALL-ed (which sqlmesh handles via the `extensions`
   list), subsequent `LOAD h3` calls succeed without the flag.
3. **Empty `rows: []` inputs need an explicit `columns:` map.** Otherwise
   the synthesized VALUES list has zero columns and SQLMesh errors with
   `Values list X does not have a column named Y` or `columns_to_types must
   be provided for dataframes`. The `columns:` map is `{col_name: TYPE}`
   alongside `rows:`.

# Residual risk

- DuckDB `ROUND(x::NUMERIC, n)` does not match hand-derived rounding for
  values ending in mid-digits (`1.234567 → 1.24`, not `1.23`). One test
  expectation hand-derived as `2.267` actually computes to `2.268`. Tests
  pin the actual DuckDB output, not the textbook value, and call this out
  inline. If DuckDB changes its NUMERIC ROUND semantics in a future bump,
  these will break and need re-derivation.
- `sqlmesh test` is now wired into `task ci` and a new `sqlmesh-test` CI
  job, but the CI job runs only on changes to source/cross-cutting paths
  (it shares the `needs_full || needs_any_source` gate with `sqlmesh-lint`).
  Pure docs PRs skip it. That matches the existing routing intent.
