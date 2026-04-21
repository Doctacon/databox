# ebird.fct_daily_bird_observations

Daily bird observation facts aggregated by region, date, and species

## Overview

| Field | Value |
| --- | --- |
| Schema | `ebird` |
| Name | `fct_daily_bird_observations` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/ebird/fct_daily_bird_observations.yaml`](https://github.com/crlough/databox/blob/main/soda/contracts/ebird/fct_daily_bird_observations.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `afternoon_observations` | `BIGINT` | — | — |
| `avg_flock_size` | `DOUBLE` | — | — |
| `avg_observations_per_location` | `DOUBLE` | — | — |
| `common_name` | `UNKNOWN` | missing (must_be=0) | — |
| `counted_observations` | `BIGINT` | — | — |
| `evening_observations` | `BIGINT` | — | — |
| `family_common_name` | `UNKNOWN` | — | — |
| `first_loaded_at` | `UNKNOWN` | — | — |
| `flock_observations` | `BIGINT` | — | — |
| `last_loaded_at` | `UNKNOWN` | — | — |
| `last_updated_at` | `TIMESTAMP` | — | — |
| `location_count` | `BIGINT` | — | — |
| `max_flock_size` | `UNKNOWN` | — | — |
| `morning_observations` | `BIGINT` | — | — |
| `night_observations` | `BIGINT` | — | — |
| `notable_observations` | `BIGINT` | — | — |
| `observation_count` | `BIGINT` | missing (must_be=0) | — |
| `observation_date` | `UNKNOWN` | missing (must_be=0) | — |
| `pct_counted_observations` | `DOUBLE` | — | — |
| `pct_valid_observations` | `DOUBLE` | — | — |
| `popularity_score` | `DOUBLE` | — | — |
| `presence_only_observations` | `BIGINT` | — | — |
| `region_code` | `UNKNOWN` | missing (must_be=0) | — |
| `reviewed_observations` | `BIGINT` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `season` | `TEXT` | — | — |
| `species_code` | `UNKNOWN` | missing (must_be=0) | — |
| `submission_count` | `BIGINT` | — | — |
| `taxonomic_category` | `UNKNOWN` | — | — |
| `total_birds_counted` | `UNKNOWN` | — | — |
| `unique_locations_approx` | `BIGINT` | — | — |
| `valid_observations` | `BIGINT` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=last_updated_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- [`ebird.int_ebird_enriched_observations`](int_ebird_enriched_observations.md)

**Downstream**

- [`analytics.fct_bird_weather_daily`](../analytics/fct_bird_weather_daily.md)

## Example query

```sql
SELECT * FROM ebird.fct_daily_bird_observations LIMIT 100;
```
