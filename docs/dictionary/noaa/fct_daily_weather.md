# noaa.fct_daily_weather

Daily weather facts pivoted from normalized observations to one row per station per date

## Overview

| Field | Value |
| --- | --- |
| Schema | `noaa` |
| Name | `fct_daily_weather` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/noaa/fct_daily_weather.yaml`](https://github.com/crlough/databox/blob/main/soda/contracts/noaa/fct_daily_weather.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `awnd` | `DOUBLE` | — | — |
| `days_with_tmax_7d` | `BIGINT` | — | — |
| `first_loaded_at` | `TIMESTAMP` | — | — |
| `last_loaded_at` | `TIMESTAMP` | — | — |
| `last_updated_at` | `TIMESTAMP` | — | — |
| `location_id` | `UNKNOWN` | — | — |
| `missing_value_count` | `BIGINT` | — | — |
| `observation_count` | `BIGINT` | — | — |
| `observation_date` | `DATE` | missing (must_be=0) | — |
| `pct_data_completeness` | `DOUBLE` | — | — |
| `prcp` | `DOUBLE` | — | — |
| `snow` | `DOUBLE` | — | — |
| `station` | `UNKNOWN` | missing (must_be=0) | — |
| `temp_range` | `DOUBLE` | — | — |
| `tmax` | `DOUBLE` | — | — |
| `tmin` | `DOUBLE` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=last_updated_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- [`noaa_staging.stg_noaa_daily_weather`](../noaa_staging/stg_noaa_daily_weather.md)

**Downstream**

- [`analytics.fct_bird_weather_daily`](../analytics/fct_bird_weather_daily.md)
- [`noaa.int_weather_by_h3_day`](int_weather_by_h3_day.md)

## Example query

```sql
SELECT * FROM noaa.fct_daily_weather LIMIT 100;
```
