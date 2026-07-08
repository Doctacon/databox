# environmental_observations.dim_weather_station

CDM NOAA weather station dimension.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `dim_weather_station` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/dim_weather_station.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/dim_weather_station.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `data_coverage` | `UNKNOWN` | — | — |
| `elevation` | `UNKNOWN` | — | — |
| `elevation_unit` | `UNKNOWN` | — | — |
| `latitude` | `UNKNOWN` | — | — |
| `loaded_at` | `UNKNOWN` | — | — |
| `location_id` | `UNKNOWN` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `max_date` | `UNKNOWN` | — | — |
| `min_date` | `UNKNOWN` | — | — |
| `source_id` | `UNKNOWN` | — | — |
| `source_pipeline` | `UNKNOWN` | — | — |
| `station_id` | `UNKNOWN` | — | — |
| `station_name` | `UNKNOWN` | — | — |
| `weather_station_sk` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_noaa.stations` (external)

**Downstream**

- [`environmental_observations.fact_weather_observation`](fact_weather_observation.md)

## Example query

```sql
SELECT * FROM environmental_observations.dim_weather_station LIMIT 100;
```
