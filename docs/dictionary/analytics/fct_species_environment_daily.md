# analytics.fct_species_environment_daily

Flagship cross-domain mart: bird observations joined to daily weather and streamflow at species x H3 cell (resolution 6, ~36 km^2) x day grain. Answers questions like "which species show up on cold-snap days after heavy rainfall at this gauge." Grain is unique on (species_code, h3_cell, obs_date).

## Overview

| Field | Value |
| --- | --- |
| Schema | `analytics` |
| Name | `fct_species_environment_daily` |
| Kind | `FULL` |
| Grain | `(species_code, h3_cell, obs_date)` |
| Soda contract | [`soda/contracts/analytics/fct_species_environment_daily.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/analytics/fct_species_environment_daily.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `cell_center_lat` | `double` | — | — |
| `cell_center_lng` | `double` | — | — |
| `common_name` | `text` | — | — |
| `discharge_cfs_z_7d` | `DOUBLE` | — | — |
| `ebird_last_loaded_at` | `timestamp` | — | — |
| `h3_cell` | `text` | missing (must_be=0) | — |
| `is_hot_day` | `INT` | — | — |
| `is_rainy_day` | `BOOLEAN` | — | — |
| `last_updated_at` | `TIMESTAMP` | — | — |
| `mean_discharge_cfs` | `DOUBLE` | — | — |
| `mean_gage_height_ft` | `DOUBLE` | — | — |
| `mean_water_temp_c` | `DOUBLE` | — | — |
| `n_checklists` | `BIGINT` | — | — |
| `n_notable_observations` | `BIGINT` | — | — |
| `n_observations` | `BIGINT` | missing (must_be=0) | — |
| `nearest_gauge_distance_miles` | `DOUBLE` | — | — |
| `nearest_gauge_id` | `text` | — | — |
| `nearest_station_distance_miles` | `DOUBLE` | — | — |
| `nearest_station_id` | `text` | — | — |
| `noaa_last_loaded_at` | `TIMESTAMP` | — | — |
| `obs_date` | `date` | missing (must_be=0) | — |
| `prcp_mm` | `DOUBLE` | — | — |
| `prcp_mm_z_7d` | `DOUBLE` | — | — |
| `scientific_name` | `text` | — | — |
| `snow_mm` | `DOUBLE` | — | — |
| `species_code` | `text` | missing (must_be=0) | — |
| `temp_range_c` | `DOUBLE` | — | — |
| `tmax_c` | `DOUBLE` | — | — |
| `tmin_c` | `DOUBLE` | — | — |
| `total_birds_counted` | `bigint` | — | — |
| `usgs_last_loaded_at` | `TIMESTAMP` | — | — |
| `wind_ms` | `DOUBLE` | — | — |

## Table-level checks

- **duplicate** — columns=['species_code', 'h3_cell', 'obs_date'], must_be=0
- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- [`ebird.int_observations_by_h3_day`](../ebird/int_observations_by_h3_day.md)
- [`noaa.int_weather_by_h3_day`](../noaa/int_weather_by_h3_day.md)
- [`usgs.int_streamflow_by_h3_day`](../usgs/int_streamflow_by_h3_day.md)

## Example query

```sql
SELECT * FROM analytics.fct_species_environment_daily LIMIT 100;
```
