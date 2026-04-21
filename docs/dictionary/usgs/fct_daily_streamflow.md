# usgs.fct_daily_streamflow

Daily streamflow facts pivoted to one row per site per date with key hydrological metrics

## Overview

| Field | Value |
| --- | --- |
| Schema | `usgs` |
| Name | `fct_daily_streamflow` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/usgs/fct_daily_streamflow.yaml`](https://github.com/crlough/databox/blob/main/soda/contracts/usgs/fct_daily_streamflow.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `discharge_7d_avg_cfs` | `DOUBLE` | — | — |
| `discharge_cfs` | `UNKNOWN` | — | — |
| `drainage_area_sqmi` | `UNKNOWN` | — | — |
| `first_loaded_at` | `TIMESTAMP` | — | — |
| `gage_height_ft` | `UNKNOWN` | — | — |
| `huc_cd` | `UNKNOWN` | — | — |
| `last_loaded_at` | `TIMESTAMP` | — | — |
| `last_updated_at` | `TIMESTAMP` | — | — |
| `latitude` | `UNKNOWN` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `observation_date` | `DATE` | missing (must_be=0) | — |
| `parameter_count` | `BIGINT` | — | — |
| `site_name` | `UNKNOWN` | — | — |
| `site_no` | `UNKNOWN` | missing (must_be=0) | — |
| `state_cd` | `UNKNOWN` | — | — |
| `water_temp_c` | `UNKNOWN` | — | — |
| `water_temp_f` | `DOUBLE` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=last_updated_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- [`usgs_staging.stg_usgs_daily_values`](../usgs_staging/stg_usgs_daily_values.md)
- [`usgs_staging.stg_usgs_sites`](../usgs_staging/stg_usgs_sites.md)

**Downstream**

- [`usgs.int_streamflow_by_h3_day`](int_streamflow_by_h3_day.md)

## Example query

```sql
SELECT * FROM usgs.fct_daily_streamflow LIMIT 100;
```
