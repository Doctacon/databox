---
id: ticket:semantic-metrics-layer
kind: ticket
status: ready
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 3
depends_on:
  - ticket:flagship-cross-domain-mart
---

# Goal

Introduce a thin semantic/metrics layer over `analytics.fct_species_environment_daily` so consumers (Dive dashboards, ad-hoc queries, future BI tools) share one definition of each metric.

# Why

Metric sprawl — the same KPI computed five slightly different ways across five dashboards — is the failure mode staff-level engineers are hired to prevent. Having a named, tested semantic layer in a portfolio repo is a direct signal of that awareness, even at single-operator scale.

# In Scope

- Evaluate and pick one of: SQLMesh metrics (if mature enough in current version), MetricFlow standalone, or a flat `analytics.metrics_*` convention — whichever respects the constitution's "fewer, stronger tools" principle
- Define at least five metrics over the flagship mart:
  - `species_richness` — distinct species per (h3_cell, date)
  - `observation_intensity` — observations per checklist per (h3_cell, date)
  - `heat_stress_index` — derived from tmax thresholds per day
  - `rainfall_anomaly_7d` — 7-day rolling precipitation z-score per cell
  - `discharge_anomaly_7d` — analogous for streamflow
- Per-metric SQLMesh tests (at least a "not null on non-empty input" check)
- `docs/metrics.md` documenting definition, grain, and owner for each
- Dive (or plain Streamlit) preview that reads metrics by name, not by ad-hoc SQL

# Out of Scope

- Adding Cube.js, dbt Semantic Layer, or any new OSS framework outside the existing stack unless evaluation strongly demands it — prefer SQLMesh-native if viable
- Row-level security / access controls
- User-facing metric self-service UI
- Backfilling metrics across multiple historical marts

# Acceptance Criteria

- Each metric resolves to a single canonical SQL definition, reachable by a stable identifier
- Consumers request the metric by name (not copy-pasted SQL) in at least one example notebook or Dive view
- Each metric has a SQLMesh-style test that fails on regressions
- `docs/metrics.md` describes each metric's definition, units, grain, and known caveats
- A written decision record in `.loom/research/` captures why the chosen approach beat the alternatives

# Approach Notes

- Before committing, skim SQLMesh current-release notes for metrics support — if it's shipped and stable, use it. Otherwise fall back to disciplined `analytics.metric_*` views.
- Do not over-engineer: five metrics that tell a coherent story beat twenty-five that don't
- Anomaly metrics need enough history (30+ days) to be meaningful — align with the flagship mart's retention window

# Evidence Expectations

- Link to the research record capturing the approach decision
- Each metric's definition link
- Screenshot of the Dive view or notebook pulling metrics by name
