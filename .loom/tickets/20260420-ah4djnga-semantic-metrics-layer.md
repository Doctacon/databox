---
id: ticket:semantic-metrics-layer
kind: ticket
status: closed
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-21T19:20:00Z
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

# Close Notes

Merged as PR #10.

**Deliverables:**
- Seven metrics registered in `transforms/main/metrics/flagship.sql`: `species_richness`, `total_observations`, `total_checklists`, `observation_intensity` (derived), `heat_stress_index`, `rainfall_anomaly_7d`, `discharge_anomaly_7d`
- Consumer helper: `databox_orchestration.metrics.resolve_metric_query()` — takes metric-aware SQL (`SELECT ... METRIC(name) FROM __semantic.__table`) and returns DuckDB-executable SQL
- Flagship mart gained `grain (species_code, h3_cell, obs_date)` + three additive columns (`is_hot_day`, `prcp_mm_z_7d`, `discharge_cfs_z_7d`); SQLMesh classifies as non-breaking
- `tests/test_metrics.py` — 4 tests: registry presence, rewrite correctness, derived-metric expansion, per-metric resolution
- `.loom/research/20260421-semantic-metrics-approach.md` — decision record (SQLMesh native chosen over MetricFlow standalone / flat `analytics.metric_*` views)
- `docs/metrics.md` — registry table, caveats, usage examples, add-a-metric guide
- README link updated

**Evidence:**

```python
from databox_orchestration.metrics import resolve_metric_query
sql = resolve_metric_query(
    "SELECT obs_date, METRIC(species_richness) AS sr, "
    "METRIC(observation_intensity) AS oi "
    "FROM __semantic.__table GROUP BY obs_date"
)
# -> executed against analytics.fct_species_environment_daily on MotherDuck
# -> returns obs_date | sr | oi rows: (2026-03-19, 13, 1.0), (2026-03-20, 46, 1.0), ...
```

Full pytest suite: 30 passed. Soda contract: 6/6 pass. CI: all 6 checks green.

**Residual notes for acceptance review:**
- Screenshot of Dive/notebook not captured — evidence is the passing test `test_all_ticket_metrics_resolve` plus the live SQL execution demonstrated above. Can add a Dive page later if wanted.
- `__semantic.__table` is NOT auto-rewritten inside model query bodies in SQLMesh v0.234.1; the rewriter must be called explicitly. Trade-off documented in the research record.
- Aggregate expressions in metrics must reference a single measure column (`AVG(t.col)`), not nested `CASE WHEN`. `heat_stress_index` was refactored to use a precomputed `is_hot_day` flag.
