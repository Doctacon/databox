# usgs_staging.stg_usgs_daily_values

Staging model for USGS daily streamflow and gage observations

## Overview

| Field | Value |
| --- | --- |
| Schema | `usgs_staging` |
| Name | `stg_usgs_daily_values` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/usgs_staging/stg_usgs_daily_values.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/usgs_staging/stg_usgs_daily_values.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `latitude` | `UNKNOWN` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `observation_date` | `DATE` | missing (must_be=0) | — |
| `parameter_cd` | `UNKNOWN` | missing (must_be=0) | — |
| `parameter_name` | `UNKNOWN` | — | — |
| `qualifier` | `UNKNOWN` | — | — |
| `site_name` | `UNKNOWN` | — | — |
| `site_no` | `UNKNOWN` | missing (must_be=0) | — |
| `state_cd` | `UNKNOWN` | — | — |
| `unit_cd` | `UNKNOWN` | — | — |
| `value` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=loaded_at, threshold={'unit': 'hour', 'must_be_less_than': 168}

## Lineage

**Upstream**

- `main.daily_values` (external)

**Downstream**

- [`usgs.fct_daily_streamflow`](../usgs/fct_daily_streamflow.md)

## Example query

```sql
SELECT * FROM usgs_staging.stg_usgs_daily_values LIMIT 100;
```
