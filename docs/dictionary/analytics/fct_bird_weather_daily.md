# analytics.fct_bird_weather_daily

eBird daily observations joined with NOAA weather conditions — one row per region x date x species

## Overview

| Field | Value |
| --- | --- |
| Schema | `analytics` |
| Name | `fct_bird_weather_daily` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/analytics/fct_bird_weather_daily.yaml`](https://github.com/crlough/databox/blob/main/soda/contracts/analytics/fct_bird_weather_daily.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `avg_flock_size` | `DOUBLE` | — | — |
| `avg_prcp_mm` | `DOUBLE` | — | — |
| `avg_snow_mm` | `DOUBLE` | — | — |
| `avg_tmax_c` | `DOUBLE` | — | — |
| `avg_tmin_c` | `DOUBLE` | — | — |
| `avg_wind_ms` | `DOUBLE` | — | — |
| `common_name` | `UNKNOWN` | missing (must_be=0) | — |
| `daily_temp_range_c` | `DOUBLE` | — | — |
| `family_common_name` | `UNKNOWN` | — | — |
| `is_rainy_day` | `BOOLEAN` | — | — |
| `last_updated_at` | `TIMESTAMP` | — | — |
| `location_count` | `BIGINT` | — | — |
| `notable_observations` | `BIGINT` | — | — |
| `observation_count` | `BIGINT` | missing (must_be=0) | — |
| `observation_date` | `UNKNOWN` | missing (must_be=0) | — |
| `popularity_score` | `DOUBLE` | — | — |
| `region_code` | `UNKNOWN` | missing (must_be=0) | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `season` | `TEXT` | — | — |
| `species_code` | `UNKNOWN` | missing (must_be=0) | — |
| `submission_count` | `BIGINT` | — | — |
| `taxonomic_category` | `UNKNOWN` | — | — |
| `total_birds_counted` | `UNKNOWN` | — | — |
| `weather_station_count` | `BIGINT` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=last_updated_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- [`ebird.fct_daily_bird_observations`](../ebird/fct_daily_bird_observations.md)
- [`noaa.fct_daily_weather`](../noaa/fct_daily_weather.md)

**Downstream**

- [`analytics.fct_species_weather_preferences`](fct_species_weather_preferences.md)

## Example query

```sql
SELECT * FROM analytics.fct_bird_weather_daily LIMIT 100;
```
