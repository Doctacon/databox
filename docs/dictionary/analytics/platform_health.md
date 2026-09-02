# analytics.platform_health

Per-source load observability — most recent dlt load id, completion time, status, and row volume. One row per source.

## Overview

| Field | Value |
| --- | --- |
| Schema | `analytics` |
| Name | `platform_health` |
| Kind | `VIEW` |
| Soda contract | [`soda/contracts/analytics/platform_health.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/analytics/platform_health.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `age` | `UNKNOWN` | — | — |
| `completed_at` | `UNKNOWN` | missing (must_be=0) | — |
| `load_id` | `UNKNOWN` | missing (must_be=0) | — |
| `rows_loaded` | `UNKNOWN` | — | — |
| `schema_name` | `UNKNOWN` | — | — |
| `source` | `UNKNOWN` | missing (must_be=0), invalid (valid_values=['ebird', 'gbif', 'xeno_canto', 'noaa', 'usgs', 'usgs_earthquakes'], must_be=0) | — |
| `status` | `UNKNOWN` | missing (must_be=0) | — |
| `status_label` | `TEXT` | — | — |

## Table-level checks

- **row_count** — must_be=6

## Lineage

**Upstream**

- `raw_avonet._dlt_load_status` (external)
- `raw_ebird._dlt_load_status` (external)
- `raw_gbif._dlt_load_status` (external)
- `raw_noaa._dlt_load_status` (external)
- `raw_usfws._dlt_load_status` (external)
- `raw_usgs._dlt_load_status` (external)
- `raw_usgs_earthquakes._dlt_load_status` (external)
- `raw_xeno_canto._dlt_load_status` (external)

## Example query

```sql
SELECT * FROM analytics.platform_health LIMIT 100;
```
