# Semantic Metrics

Canonical metric definitions now sit on the CDM fact model
`environmental_observations.fact_bird_observation`. Every metric below is
registered in `transforms/main/metrics/flagship.sql` and is the single source of
truth.

## Registry

| Metric | Grain | Units | Definition |
|---|---|---|---|
| `species_richness` | any group | count | Distinct `species_code` in the group. |
| `total_observations` | any group | count | Count of distinct `bird_observation_sk` fact rows. |
| `total_observed_birds` | any group | count | Sum of `observation_count`; null/X counts are ignored by SQL `SUM` semantics. |

"Any group" means any grouping supported by the CDM bird-observation fact, such
as `observation_date`, `species_code`, `location_id`, `region_code`, or a
combination.

## Usage

Consumers request metrics by name, not by copy-pasted SQL.

```python
from databox.orchestration.metrics import resolve_metric_query

sql = resolve_metric_query(
    """
    SELECT observation_date,
           METRIC(species_richness) AS species_richness,
           METRIC(total_observations) AS total_observations,
           METRIC(total_observed_birds) AS total_observed_birds
    FROM __semantic.__table
    GROUP BY observation_date
    ORDER BY observation_date
    """
)
# `sql` is DuckDB-ready SQL against
# environmental_observations.fact_bird_observation.
```

### Listing available metrics

```python
from databox.orchestration.metrics import available_metrics
print(available_metrics())
# -> ['species_richness', 'total_observations', 'total_observed_birds']
```

## Adding a new metric

1. Add a `METRIC (name=..., expression=...)` block to
   `transforms/main/metrics/flagship.sql`.
2. Fully qualify column references with
   `environmental_observations.fact_bird_observation.<col>` or another active
   CDM model.
3. Add the metric name to `REQUIRED_METRICS` in `tests/test_metrics.py` if it is
   required behavior.
4. Document the metric in the registry table above.
5. Run `uv run pytest tests/test_metrics.py`.
