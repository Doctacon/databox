# environmental_observations.fact_weather_observation

CDM fact: one row per NOAA station per observation date per datatype.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `fact_weather_observation` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/fact_weather_observation.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/fact_weather_observation.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `attributes` | `UNKNOWN` | — | — |
| `datatype` | `UNKNOWN` | — | — |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `location_id` | `UNKNOWN` | — | — |
| `observation_date` | `DATE` | — | — |
| `source` | `UNKNOWN` | — | — |
| `source_id` | `TEXT` | — | — |
| `source_pipeline` | `TEXT` | — | — |
| `station_id` | `UNKNOWN` | — | — |
| `value` | `DOUBLE` | — | — |
| `weather_observation_sk` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `weather_station_sk` | `UNKNOWN` | missing (must_be=0) | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- [`environmental_observations.dim_weather_station`](dim_weather_station.md)
- `raw_noaa.daily_weather` (external)

## Example query

```sql
SELECT * FROM environmental_observations.fact_weather_observation LIMIT 100;
```
