# usgs_staging.stg_usgs_sites

Staging model for USGS monitoring site metadata

## Overview

| Field | Value |
| --- | --- |
| Schema | `usgs_staging` |
| Name | `stg_usgs_sites` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/usgs_staging/stg_usgs_sites.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/usgs_staging/stg_usgs_sites.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `begin_date` | `UNKNOWN` | — | — |
| `county_cd` | `UNKNOWN` | — | — |
| `drainage_area_sqmi` | `UNKNOWN` | — | — |
| `end_date` | `UNKNOWN` | — | — |
| `huc_cd` | `UNKNOWN` | — | — |
| `latitude` | `UNKNOWN` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `site_name` | `UNKNOWN` | — | — |
| `site_no` | `UNKNOWN` | missing (must_be=0) | — |
| `site_type` | `UNKNOWN` | — | — |
| `state_cd` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=loaded_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- `main.sites` (external)

**Downstream**

- [`usgs.fct_daily_streamflow`](../usgs/fct_daily_streamflow.md)
- [`usgs.int_streamflow_by_h3_day`](../usgs/int_streamflow_by_h3_day.md)

## Example query

```sql
SELECT * FROM usgs_staging.stg_usgs_sites LIMIT 100;
```
