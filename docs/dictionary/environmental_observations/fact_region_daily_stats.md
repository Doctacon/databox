# environmental_observations.fact_region_daily_stats

CDM fact: one row per eBird region per calendar date.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `fact_region_daily_stats` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/fact_region_daily_stats.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/fact_region_daily_stats.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `day` | `UNKNOWN` | — | — |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `month` | `UNKNOWN` | — | — |
| `num_checklists` | `UNKNOWN` | — | — |
| `num_contributors` | `UNKNOWN` | — | — |
| `num_species` | `UNKNOWN` | — | — |
| `region_code` | `UNKNOWN` | — | — |
| `region_daily_stats_sk` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `source_id` | `TEXT` | — | — |
| `source_pipeline` | `TEXT` | — | — |
| `stats_date` | `DATE` | — | — |
| `year` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_ebird.region_stats` (external)

## Example query

```sql
SELECT * FROM environmental_observations.fact_region_daily_stats LIMIT 100;
```
