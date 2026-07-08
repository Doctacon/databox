# environmental_observations.dim_streamgage_site

CDM USGS streamgage site dimension.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `dim_streamgage_site` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/dim_streamgage_site.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/dim_streamgage_site.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `begin_date` | `UNKNOWN` | — | — |
| `county_cd` | `UNKNOWN` | — | — |
| `drainage_area_sqmi` | `UNKNOWN` | — | — |
| `end_date` | `UNKNOWN` | — | — |
| `huc_cd` | `UNKNOWN` | — | — |
| `latitude` | `UNKNOWN` | — | — |
| `loaded_at` | `UNKNOWN` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `site_name` | `UNKNOWN` | — | — |
| `site_no` | `UNKNOWN` | — | — |
| `site_type` | `UNKNOWN` | — | — |
| `source_id` | `UNKNOWN` | — | — |
| `source_pipeline` | `UNKNOWN` | — | — |
| `state_cd` | `UNKNOWN` | — | — |
| `streamgage_site_sk` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_usgs.sites` (external)

**Downstream**

- [`environmental_observations.fact_streamflow_observation`](fact_streamflow_observation.md)

## Example query

```sql
SELECT * FROM environmental_observations.dim_streamgage_site LIMIT 100;
```
