---
id: research:semantic-metrics-approach
kind: research
status: active
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: repository
  repositories:
    - repo:root
links:
  ticket: ticket:semantic-metrics-layer
  plan: plan:staff-portfolio-readiness
---

# Question

Which semantic/metrics layer approach best fits a single-operator, zero-cost
data platform whose constitution favors "fewer, stronger tools"? Candidates:

1. **SQLMesh native `METRIC()` DDL** — built into the transformation engine
   already in the stack (v0.234.1).
2. **MetricFlow standalone** — dbt Labs' semantic layer, operable outside dbt.
3. **Flat `analytics.metric_*` views** — one SQLMesh view per metric, no
   additional tooling.

# Decision

**Adopt SQLMesh native `METRIC()` DDL.** The metrics live in
`transforms/main/metrics/flagship.sql` and consumers resolve them via a thin
Python helper (`databox_orchestration.metrics.resolve_metric_query`) that
wraps SQLMesh's metric rewriter.

# Evaluation

## SQLMesh `METRIC()` (chosen)

- Lives inside the existing SQLMesh project — zero new dependencies, no
  second config surface.
- Supports derived metrics (e.g. `observation_intensity = total_observations
  / NULLIF(total_checklists, 0)`); the rewriter auto-hoists the raw
  aggregates the derived metric needs, so consumers just ask for the
  derived name.
- Requires model `grain` to be declared on the underlying mart — already
  aligned with our flagship mart's uniqueness key
  `(species_code, h3_cell, obs_date)`.
- Caveat: the documented `SELECT METRIC(...) FROM __semantic.__table`
  syntax is **not** automatically expanded inside model query bodies in
  v0.234.1. The rewriter must be invoked explicitly (see
  `sqlmesh.core.metric.rewriter.rewrite`). Acceptable trade — we wrap it in
  `resolve_metric_query()` and consumers call that function; they never
  see the raw rewriter.
- Caveat: aggregate expressions must reference a single measure column
  (e.g. `AVG(t.col)`) — wrapping `CASE WHEN` directly inside the aggregate
  trips "Could not infer a measures table from..." We work around this by
  adding precomputed `is_hot_day` column to the mart rather than computing
  it inside the metric expression.

## MetricFlow standalone (rejected)

- Powerful semantic model (entities, dimensions, measures, time grains)
  but requires its own YAML dialect, Python runtime, and server process
  for query resolution.
- Project-level overhead is disproportionate for a single flagship mart
  with seven metrics.
- Violates constitution principle #4 ("fewer, stronger tools"): adds a new
  tool with significant conceptual footprint alongside SQLMesh.

## Flat `analytics.metric_*` views (rejected)

- Cheapest in tooling: one view per metric, zero new abstractions.
- No first-class notion of a "metric"; consumers would still have to
  remember which view computes what. Derived metrics (e.g. ratios) would
  duplicate SQL across views.
- Signals lack of awareness of the metric-sprawl problem the ticket is
  designed to address.

# Consequences

- Metric definitions live in one place (`transforms/main/metrics/flagship.sql`).
- Consumers (Dagster, notebooks, Streamlit) import
  `databox_orchestration.metrics.resolve_metric_query`, pass a query using
  `METRIC(...)` syntax, and receive executable SQL.
- Adding a new metric = add a `METRIC (...)` block + list it in
  `docs/metrics.md`. No new models, no new consumers to update.
- The `is_hot_day` flag on the flagship mart is load-bearing for the
  `heat_stress_index` metric; removing it would break metric resolution.

# References

- SQLMesh metrics docs:
  https://sqlmesh.readthedocs.io/en/stable/concepts/metrics/overview/
- SQLMesh metrics definition:
  https://sqlmesh.readthedocs.io/en/stable/concepts/metrics/definition/
- Internal: `packages/databox-orchestration/databox_orchestration/metrics.py`
- Internal: `tests/test_metrics.py`
