---
id: ticket:flagship-cross-domain-mart
kind: ticket
status: complete_pending_acceptance
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 3
depends_on:
  - ticket:source-test-harness
  - ticket:schema-contract-ci
---

# Goal

Build the flagship cross-domain mart that makes the platform's purpose legible in one table: bird observations joined to daily weather and streamflow, at a spatial grain small enough to answer questions like "which species show up on cold-snap days after heavy rainfall at this gauge."

Proposed model: `analytics.fct_species_environment_daily` (grain: species × H3 cell × day).

# Why

The constitution says cross-domain joins are the point. Today the repo has three isolated source domains and no mart that actually crosses them. A recruiter clicking into `transforms/main/models/analytics/` should see the platform delivering on its own thesis.

# In Scope

- One intermediate model per source aligning to a shared spatial/temporal grain:
  - `ebird.int_observations_by_h3_day` — bird observations rolled up to H3 cell × day
  - `noaa.int_weather_by_h3_day` — nearest-station weather metrics assigned to H3 cells via spatial join
  - `usgs.int_streamflow_by_h3_day` — nearest gauge streamflow assigned to H3 cells
- Mart: `analytics.fct_species_environment_daily`
  - dimensions: `species_code`, `h3_cell`, `obs_date`
  - measures: `n_observations`, `n_checklists`, `tmax_c`, `tmin_c`, `prcp_mm`, `snow_mm`, `mean_discharge_cfs`, `nearest_gauge_id`
  - H3 resolution 6 or 7 (roughly 5–36 km²) — pick and document
- Soda contract covering the mart (uniqueness on grain, null checks on dims, reasonable range checks)
- Dagster asset wiring, freshness policy, asset check
- Example analytical queries in `docs/analytics-examples.md`

# Out of Scope

- Multi-year backfill validation — daily cadence only, last 90 days is enough for the portfolio
- A published dashboard — mart alone is the deliverable; dashboarding handled in existing Dive/Streamlit surface
- Species-taxonomy enrichment beyond what `ebird` already provides
- Rebuilding the `ebird_staging` / `noaa_staging` / `usgs_staging` layers

# Acceptance Criteria

- `sqlmesh run` builds the mart end-to-end from a fresh DuckDB
- Row count at grain is stable across three consecutive runs (idempotency)
- Soda contract passes, including uniqueness on (`species_code`, `h3_cell`, `obs_date`)
- Mart has descriptive column comments and a model-level description
- At least three example queries in `docs/analytics-examples.md` answer non-trivial questions (e.g. species diversity vs. precipitation)
- Dagster UI shows the mart asset with upstream lineage crossing all three source domains

# Approach Notes

- DuckDB's `h3` community extension or the pre-installed `spatial` extension handles H3 indexing — prefer whichever is already available in the pipeline runtime
- "Nearest station/gauge" is a spatial join with `ST_Distance` — precompute a station-to-H3 mapping table, don't recompute per-day
- Start with H3 resolution 6, measure cardinality, adjust if row count explodes
- The intermediate models are reusable — future marts should join on the same H3 × day grain

# Evidence Expectations

- `SELECT COUNT(*), MIN(obs_date), MAX(obs_date) FROM analytics.fct_species_environment_daily` in the ticket close notes
- Screenshot of the Dagster asset graph showing the cross-domain lineage
- Link to `docs/analytics-examples.md`

# Close Notes

Merged as PR #9 (commit 39bc596, squashed).

**Deliverables:**
- `ebird.int_observations_by_h3_day` — species × H3 (res 6) × day aggregate
- `noaa.int_weather_by_h3_day` — nearest-station weather via haversine join
- `usgs.int_streamflow_by_h3_day` — nearest-gauge streamflow via haversine join
- `analytics.fct_species_environment_daily` — LEFT-joined mart, unique on `(species_code, h3_cell, obs_date)`, rounds env measures, adds `temp_range_c`, `is_rainy_day`, cell centroid lat/lng, per-source `*_last_loaded_at`, `last_updated_at`
- `soda/contracts/analytics/fct_species_environment_daily.yaml` — 6 checks, all pass locally
- Dagster wiring in `definitions.py` (`_analytics_sqlmesh_keys`, `_soda_checks`)
- `docs/analytics-examples.md` with four example queries
- h3 community extension added to both SQLMesh gateways (`local`, `motherduck`)

**Evidence (MotherDuck prod):**

```
SELECT COUNT(*), MIN(obs_date), MAX(obs_date) FROM analytics.fct_species_environment_daily
-> (2275, 2026-03-19, 2026-04-18)
```

- 363 distinct species, 395 distinct H3 cells, 31 distinct days
- 0 duplicates on `(species_code, h3_cell, obs_date)`
- Soda contract: 6 checks / 6 passed / 0 failed
- `sqlmesh evaluate analytics.fct_species_environment_daily` re-runs deterministically (FULL kind + same inputs)
- Weather join coverage ~22% (NOAA GHCND publish latency — cells have a station assigned, but recent dates often lack values yet); streamflow coverage ~85%

**H3 resolution choice:** resolution 6 (~36 km² hex). On current 30-day snapshot this produced 2275 rows — tight enough to be useful, coarse enough to avoid over-fragmenting sparse bird reports. Intermediate models expose `h3_cell` as a reusable join key for future marts.

**Nearest station/gauge:** computed once per cell via haversine CROSS JOIN + `ROW_NUMBER() ... WHERE rn=1`. Skipped DuckDB `spatial` extension's `ST_Distance` to avoid requiring the `GEOGRAPHY` type path; haversine is ~10 loc of SQL and matches within meters at regional scale.

**CI:** all 6 checks green on PR #9 (ruff, mypy, pytest, SQLMesh lint, schema-contract gate, Soda structure).

**Residual notes for acceptance review:**
- Dagster asset-graph screenshot not captured (headless CI environment); lineage is declarative in `definitions.py` and visible when Dagster webserver is running locally.
- Weather-join coverage is source-latency-bound, not a bug. If it stays a concern long-term, consider falling back to the second-nearest station when the nearest lacks data for a date.
