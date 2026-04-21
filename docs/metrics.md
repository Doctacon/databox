# Semantic Metrics

Canonical metric definitions over `analytics.fct_species_environment_daily`.
Every metric below is registered in
[`transforms/main/metrics/flagship.sql`](https://github.com/Doctacon/databox/blob/main/transforms/main/metrics/flagship.sql)
and is the single source of truth — if you see metric math duplicated
elsewhere, that duplication is a bug.

## Registry

| Metric | Grain | Units | Definition |
|---|---|---|---|
| `species_richness` | any group | count | Distinct `species_code` in the group. |
| `total_observations` | any group | count | `SUM(n_observations)`. |
| `total_checklists` | any group | count | `SUM(n_checklists)`. |
| `observation_intensity` | any group | ratio | `total_observations / NULLIF(total_checklists, 0)`. Higher = more observations per checklist; a proxy for species density. |
| `heat_stress_index` | any group | 0–1 fraction | Fraction of grouped rows where `tmax_c >= 30`. Backed by the precomputed `is_hot_day` column on the mart. |
| `rainfall_anomaly_7d` | any group | z-score | Mean 7-day precipitation z-score (`(prcp - μ₇) / σ₇` per `(h3_cell, obs_date)`). Positive = wetter than local recent average. Null when the 7-day window has zero variance. |
| `discharge_anomaly_7d` | any group | z-score | Mean 7-day streamflow z-score (`(discharge - μ₇) / σ₇` per `(h3_cell, obs_date)`). Positive = higher flow than local recent average. |

"Any group" means the metric is well-defined for any `GROUP BY` the mart
supports — typically `obs_date`, `h3_cell`, `species_code`, or a
combination.

## Caveats

- **Data latency.** NOAA GHCND publishes daily weather on a 3–7 day lag; on
  any given recent date the weather/anomaly metrics are sparse (~22% of
  rows on a 30-day window). USGS streamflow is faster (~85%). Bird
  observations are same-day.
- **Anomaly warm-up.** `rainfall_anomaly_7d` and `discharge_anomaly_7d`
  require 7 days of history per cell before producing a value. On a fresh
  30-day window, expect the first ~6 days per cell to be null.
- **Zero-variance windows.** When the 7-day window has identical values
  (σ = 0), the anomaly z-score is null rather than infinite.

## Usage

Consumers request metrics by name, not by copy-pasted SQL.

### Python

```python
from databox_orchestration.metrics import resolve_metric_query

sql = resolve_metric_query(
    """
    SELECT obs_date,
           METRIC(species_richness) AS species_richness,
           METRIC(observation_intensity) AS observation_intensity,
           METRIC(heat_stress_index) AS heat_stress_index
    FROM __semantic.__table
    GROUP BY obs_date
    ORDER BY obs_date
    """
)
# `sql` is DuckDB-ready SQL against analytics.fct_species_environment_daily.
# Execute it via duckdb, motherduck, or any sqlmesh gateway.
```

### Listing available metrics

```python
from databox_orchestration.metrics import available_metrics
print(available_metrics())
# -> ['discharge_anomaly_7d', 'heat_stress_index', 'observation_intensity',
#     'rainfall_anomaly_7d', 'species_richness', 'total_checklists',
#     'total_observations']
```

## Adding a New Metric

1. Add a `METRIC (name=..., expression=...)` block to
   `transforms/main/metrics/flagship.sql`.
2. Fully qualify column references:
   `analytics.fct_species_environment_daily.<col>`.
3. If the metric needs a non-trivial per-row derivation (e.g. a `CASE`
   expression), precompute it as a column on the flagship mart — the
   SQLMesh rewriter expects `AGG(table.col)` shape, not
   `AGG(CASE WHEN ...)`.
4. Add the metric name to `REQUIRED_METRICS` in `tests/test_metrics.py`
   if it's ticket-level required.
5. Document the new metric in the registry table above.
6. Run `uv run pytest tests/test_metrics.py`.

## Design Decision

See
[`.loom/research/20260421-semantic-metrics-approach.md`](https://github.com/Doctacon/databox/blob/main/.loom/research/20260421-semantic-metrics-approach.md)
for why SQLMesh native metrics beat MetricFlow and flat `analytics.metric_*`
views for this project.
