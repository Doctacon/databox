# noaa_staging.stg_noaa_daily_weather

Staging model for NOAA daily weather observations

## Overview

| Field | Value |
| --- | --- |
| Schema | `noaa_staging` |
| Name | `stg_noaa_daily_weather` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/noaa_staging/stg_noaa_daily_weather.yaml`](https://github.com/crlough/databox/blob/main/soda/contracts/noaa_staging/stg_noaa_daily_weather.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `attributes` | `UNKNOWN` | — | — |
| `datatype` | `UNKNOWN` | missing (must_be=0) | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `location_id` | `UNKNOWN` | — | — |
| `observation_date` | `DATE` | missing (must_be=0) | — |
| `source` | `UNKNOWN` | — | — |
| `station` | `UNKNOWN` | missing (must_be=0) | — |
| `value` | `DOUBLE` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=loaded_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- `main.daily_weather` (external)

**Downstream**

- [`noaa.fct_daily_weather`](../noaa/fct_daily_weather.md)

## Example query

```sql
SELECT * FROM noaa_staging.stg_noaa_daily_weather LIMIT 100;
```
