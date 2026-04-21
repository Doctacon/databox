# analytics.fct_species_weather_preferences

Per-species weather preference aggregates — what conditions correlate with each species appearing

## Overview

| Field | Value |
| --- | --- |
| Schema | `analytics` |
| Name | `fct_species_weather_preferences` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/analytics/fct_species_weather_preferences.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/analytics/fct_species_weather_preferences.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `avg_high_temp_c` | `DOUBLE` | — | — |
| `avg_low_temp_c` | `DOUBLE` | — | — |
| `avg_precip_mm` | `DOUBLE` | — | — |
| `avg_wind_ms` | `DOUBLE` | — | — |
| `coldest_day_high_c` | `DOUBLE` | — | — |
| `common_name` | `UNKNOWN` | missing (must_be=0) | — |
| `dominant_season` | `TEXT` | — | — |
| `family_common_name` | `UNKNOWN` | — | — |
| `hottest_day_high_c` | `DOUBLE` | — | — |
| `last_updated_at` | `TIMESTAMP` | — | — |
| `p25_high_temp_c` | `DOUBLE` | — | — |
| `p75_high_temp_c` | `DOUBLE` | — | — |
| `pct_rainy_days` | `DOUBLE` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `species_code` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `taxonomic_category` | `UNKNOWN` | — | — |
| `total_observation_days` | `BIGINT` | missing (must_be=0) | — |
| `total_observations` | `BIGINT` | missing (must_be=0) | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=last_updated_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- [`analytics.fct_bird_weather_daily`](fct_bird_weather_daily.md)

## Example query

```sql
SELECT * FROM analytics.fct_species_weather_preferences LIMIT 100;
```
