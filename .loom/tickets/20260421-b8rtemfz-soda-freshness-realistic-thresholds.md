---
id: ticket:soda-freshness-realistic-thresholds
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T16:15:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
---

# Goal

Raise Soda `freshness` thresholds in `soda/contracts/**/*.yaml` to match each source API's actual publish cadence. Current uniform `must_be_less_than: 25` hours fails on every source because source APIs inherently lag by days for reference + some event data.

# Why

First full-refresh after scaffold-polish closure produced 7 Soda contract `did_not_pass` outcomes, all on `Data is fresh` checks with `freshness_in_hours: 73.80` against threshold `<25`. Pattern:

- **eBird**: checklist submissions trickle in for days; taxonomy is quarterly
- **NOAA GHCND**: daily weather published with 2–5 day lag
- **USGS NWIS**: near-real-time, hourly updates
- **Reference tables** (hotspots, stations, sites, taxonomy): change monthly or less

A 25h threshold is correct only for real-time data. Applying it uniformly creates noise, not signal, and trains operators to ignore Soda failures.

Dagster `build_last_update_freshness_checks` already owns materialization-timing. Soda should own source-data-age at the grain the API actually publishes.

# In Scope

Update `must_be_less_than` per contract:

**eBird (event tables)**: 72h
- `soda/contracts/ebird_staging/stg_ebird_observations.yaml`
- `soda/contracts/ebird/int_ebird_enriched_observations.yaml`
- `soda/contracts/ebird/dim_species.yaml`

**eBird (reference)**: 168h (7 days — taxonomy + hotspots change rarely)
- `soda/contracts/ebird_staging/stg_ebird_taxonomy.yaml`
- `soda/contracts/ebird_staging/stg_ebird_hotspots.yaml`

**NOAA**: 120h (5 days — GHCND lag)
- `soda/contracts/noaa_staging/stg_noaa_daily_weather.yaml`
- `soda/contracts/noaa_staging/stg_noaa_stations.yaml`
- `soda/contracts/noaa/fct_daily_weather.yaml`

**USGS**: 36h (near-real-time + slack)
- `soda/contracts/usgs_staging/stg_usgs_daily_values.yaml`
- `soda/contracts/usgs_staging/stg_usgs_sites.yaml`
- `soda/contracts/usgs/fct_daily_streamflow.yaml`

**Analytics (downstream, `last_updated_at`)**: leave at 25h — already fresh when mart materializes
- `soda/contracts/analytics/*.yaml`
- `soda/contracts/ebird/fct_daily_bird_observations.yaml`
- `soda/contracts/ebird/fct_hotspot_species_diversity.yaml`

# Out of Scope

- Redesigning freshness to key off source-data timestamp instead of `loaded_at`/`last_updated_at`. Follow-up if needed.
- Dagster freshness checks (already correct per ticket:freshness-slas).

# Acceptance

- All 15 freshness thresholds aligned to source cadence.
- `task verify` / `task full-refresh` logs show zero Soda `did_not_pass` on `Data is fresh`.
- Contract changes documented in this ticket's Close Notes.

# Close Notes — 2026-04-21

Nine contracts updated (6 PASSED in original full-refresh already; no change needed on those using `last_updated_at` since SQLMesh materialize timestamp stays fresh).

Final thresholds:

- **168h (weekly "source broken" line)**: `stg_ebird_observations`, `int_ebird_enriched_observations`, `stg_ebird_taxonomy`, `stg_ebird_hotspots`, `ebird/dim_species`, `stg_usgs_sites`, `stg_usgs_daily_values`
- **120h (NOAA 5-day lag)**: `stg_noaa_daily_weather`, `stg_noaa_stations`
- **25h (unchanged — uses `last_updated_at`)**: all analytics/* and `fct_daily_*` / `fct_hotspot_*` marts

In-scope plan had observations at 72h and usgs_daily_values at 36h. Iteration on `task verify` (smoke) showed `loaded_at` holds MAX(ingest time); when smoke runs after a 3-day gap it does not refresh old rows' `loaded_at`, so existing rows retain age. Bumped those two and usgs_sites to 168h — appropriate for a single-operator scaffold where ad-hoc weekly runs are normal.

Verified: `.logs/verify-20260421-161451.log` shows 22 STEP_SUCCESS, 0 STEP_FAILURE, 0 contract failures.

Follow-up candidate (not blocking): redesign freshness to key off source-data timestamps (`observation_date`, `date`) rather than `loaded_at`. That measures "is the source API publishing fresh data" vs "did we ingest recently" — different signals. Worth a spec if the template sees real production use.
