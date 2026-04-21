---
id: ticket:freshness-slas
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T19:14:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 3
depends_on:
  - ticket:definitions-split
---

# Goal

Wire Dagster `build_last_update_freshness_checks` on every mart and the flagship analytics asset. SLA thresholds declared per-source in `databox/orchestration/domains/<source>.py`. Checks fire automatically via Dagster's freshness evaluation, with structured failure output that a forker can route to their alerting channel.

# Why

ADR-0005 makes Dagster the single orchestrator. Dagster has first-class freshness checks. The scaffold today uses none of them. A forker running this in production has no way to know if data stopped flowing — a silent NOAA outage looks indistinguishable from a healthy schedule until someone queries the mart and sees stale dates.

Per-domain SLA declarations are the right place to keep these because the cadence is inherently per-source (eBird can update multiple times a day; NOAA daily weather is daily; USGS streamflow is hourly). Definitions-split created the per-domain file structure — freshness SLAs are a natural citizen of those files.

# In Scope

- For each mart and analytics asset, declare a freshness SLA as part of its asset definition:
  - `ebird.fct_daily_bird_observations` — 30h staleness tolerance (daily source + some slack)
  - `ebird.dim_species` — 7d (taxonomy doesn't change often)
  - `ebird.fct_hotspot_species_diversity` — 30h
  - `noaa.fct_daily_weather` — 48h (reports lag 1 day)
  - `usgs.fct_daily_streamflow` — 30h
  - `analytics.fct_species_environment_daily` — 48h (downstream of slowest input)
  - `analytics.platform_health` — 2h (the meta-mart itself should be fresh)
- Use `build_last_update_freshness_checks(...)` from Dagster; attach with `asset_checks=[...]` on the domain module
- Add a Dagster sensor `freshness_violation_sensor` that fires on any freshness-check failure and prints a structured log line (the forker wires it to Slack / Email / PagerDuty as they see fit — documented in `docs/runbook.md`)
- Update `platform_health` model or add a companion asset to surface freshness-check status visibly (table of mart name / last-update / SLA / status)
- `docs/freshness.md` documenting the SLA values, the rationale, and how to override per-forker

# Out of Scope

- Hooking up to a specific notification channel (forker's choice; document the wiring)
- Per-partition freshness checks — asset-level is enough for the scaffold; per-partition is an optimisation
- Latency tracking (distinct from freshness — covered under ticket:cost-observability if at all)
- Changing mart cadences (the SLAs follow current schedules)

# Acceptance Criteria

- Every mart has an explicit freshness SLA declared in its domain module
- `uv run dagster asset-check list -m databox.orchestration.definitions` shows one freshness check per covered asset
- A synthetic stale-data scenario (back-date one mart's latest row) causes the corresponding freshness check to fail and the sensor to emit its structured log line
- `docs/freshness.md` rendered in the deployed docs site, linked from README
- `platform_health` (or companion asset) shows freshness status in its materialised output
- Full-refresh on a clean checkout produces zero freshness-check failures

# Approach Notes

- `build_last_update_freshness_checks` needs an `AssetKey` list and a `maximum_lag` — prefer `datetime.timedelta` values as module-level constants so they read as a table at the top of each domain file
- The sensor should run on a short cadence (every 5 minutes) but only emit when a check transitioned from pass to fail — Dagster's event-log lookback handles this
- When a backend is `local` (file-based DuckDB), freshness checks should still work because the materialised_at metadata is recorded in Dagster state, not in the warehouse
- For `platform_health` integration: expose freshness status as a DuckDB view so it renders in the data dictionary site

# Evidence Expectations

- Screenshot / export of the Dagster asset-check panel showing the new checks green
- Synthetic-failure run (back-date a row) showing the sensor log line
- `docs/freshness.md` in the deployed docs site
- `platform_health` output including the freshness status table
