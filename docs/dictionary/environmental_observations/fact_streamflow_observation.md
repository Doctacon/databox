# environmental_observations.fact_streamflow_observation

CDM fact: one row per USGS streamgage site per observation date per parameter code.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `fact_streamflow_observation` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/fact_streamflow_observation.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/fact_streamflow_observation.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `latitude` | `DOUBLE` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `longitude` | `DOUBLE` | — | — |
| `observation_date` | `DATE` | — | — |
| `parameter_cd` | `UNKNOWN` | — | — |
| `parameter_name` | `UNKNOWN` | — | — |
| `qualifier` | `UNKNOWN` | — | — |
| `site_name` | `UNKNOWN` | — | — |
| `site_no` | `UNKNOWN` | — | — |
| `source_id` | `TEXT` | — | — |
| `source_pipeline` | `TEXT` | — | — |
| `state_cd` | `UNKNOWN` | — | — |
| `streamflow_observation_sk` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `streamgage_site_sk` | `UNKNOWN` | missing (must_be=0) | — |
| `unit_cd` | `UNKNOWN` | — | — |
| `value` | `DOUBLE` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- [`environmental_observations.dim_streamgage_site`](dim_streamgage_site.md)
- `raw_usgs.daily_values` (external)

## Example query

```sql
SELECT * FROM environmental_observations.fact_streamflow_observation LIMIT 100;
```
