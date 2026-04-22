# noaa_staging.stg_noaa_stations

Staging model for NOAA weather stations

## Overview

| Field | Value |
| --- | --- |
| Schema | `noaa_staging` |
| Name | `stg_noaa_stations` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/noaa_staging/stg_noaa_stations.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/noaa_staging/stg_noaa_stations.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `data_coverage` | `DOUBLE` | — | — |
| `elevation` | `DOUBLE` | — | — |
| `elevation_unit` | `UNKNOWN` | — | — |
| `latitude` | `DOUBLE` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `location_id` | `UNKNOWN` | — | — |
| `longitude` | `DOUBLE` | — | — |
| `max_date` | `DATE` | — | — |
| `min_date` | `DATE` | — | — |
| `station_id` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `station_name` | `UNKNOWN` | missing (must_be=0) | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=loaded_at, threshold={'unit': 'hour', 'must_be_less_than': 120}

## Lineage

**Upstream**

- `main.stations` (external)

**Downstream**

- [`noaa.int_weather_by_h3_day`](../noaa/int_weather_by_h3_day.md)

## Example query

```sql
SELECT * FROM noaa_staging.stg_noaa_stations LIMIT 100;
```
