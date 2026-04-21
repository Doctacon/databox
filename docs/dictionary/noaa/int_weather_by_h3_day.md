# noaa.int_weather_by_h3_day

Daily NOAA weather assigned to each H3 cell in the bird-observation universe via nearest-station join. Station-to-cell mapping is computed once; daily values join in after. H3 resolution 6 matches ebird.int_observations_by_h3_day.

## Overview

| Field | Value |
| --- | --- |
| Schema | `noaa` |
| Name | `int_weather_by_h3_day` |
| Kind | `FULL` |
| Soda contract | _none_ |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `h3_cell` | `UNKNOWN` | — | — |
| `last_loaded_at` | `TIMESTAMP` | — | — |
| `nearest_station_distance_miles` | `DOUBLE` | — | — |
| `nearest_station_id` | `UNKNOWN` | — | — |
| `observation_date` | `DATE` | — | — |
| `prcp_mm` | `DOUBLE` | — | — |
| `snow_mm` | `DOUBLE` | — | — |
| `tmax_c` | `DOUBLE` | — | — |
| `tmin_c` | `DOUBLE` | — | — |
| `wind_ms` | `DOUBLE` | — | — |

## Lineage

**Upstream**

- [`ebird.int_observations_by_h3_day`](../ebird/int_observations_by_h3_day.md)
- [`noaa.fct_daily_weather`](fct_daily_weather.md)
- [`noaa_staging.stg_noaa_stations`](../noaa_staging/stg_noaa_stations.md)

**Downstream**

- [`analytics.fct_species_environment_daily`](../analytics/fct_species_environment_daily.md)

## Example query

```sql
SELECT * FROM noaa.int_weather_by_h3_day LIMIT 100;
```
