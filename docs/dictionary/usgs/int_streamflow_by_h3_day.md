# usgs.int_streamflow_by_h3_day

Daily USGS streamflow assigned to each H3 cell in the bird-observation universe via nearest-gauge join. Cell-to-gauge mapping is computed once; daily values join in after. H3 resolution 6 matches ebird.int_observations_by_h3_day.

## Overview

| Field | Value |
| --- | --- |
| Schema | `usgs` |
| Name | `int_streamflow_by_h3_day` |
| Kind | `FULL` |
| Soda contract | _none_ |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `h3_cell` | `UNKNOWN` | — | — |
| `last_loaded_at` | `TIMESTAMP` | — | — |
| `mean_discharge_cfs` | `UNKNOWN` | — | — |
| `mean_gage_height_ft` | `UNKNOWN` | — | — |
| `mean_water_temp_c` | `UNKNOWN` | — | — |
| `nearest_gauge_distance_miles` | `DOUBLE` | — | — |
| `nearest_gauge_id` | `UNKNOWN` | — | — |
| `observation_date` | `DATE` | — | — |

## Lineage

**Upstream**

- [`ebird.int_observations_by_h3_day`](../ebird/int_observations_by_h3_day.md)
- [`usgs.fct_daily_streamflow`](fct_daily_streamflow.md)
- [`usgs_staging.stg_usgs_sites`](../usgs_staging/stg_usgs_sites.md)

**Downstream**

- [`analytics.fct_species_environment_daily`](../analytics/fct_species_environment_daily.md)

## Example query

```sql
SELECT * FROM usgs.int_streamflow_by_h3_day LIMIT 100;
```
