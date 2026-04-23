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
| `source` | `UNKNOWN` | missing (must_be=0), invalid (valid_values=['ebird', 'noaa', 'usgs'], must_be=0) | — |
| `status` | `UNKNOWN` | missing (must_be=0) | — |
| `status_label` | `TEXT` | — | — |

## Table-level checks

- **row_count** — must_be=3

## Lineage

**Upstream**

- `main._dlt_loads` (external)
- `main.hotspots` (external)
- `main.notable_observations` (external)
- `main.recent_observations` (external)
- `main.species_list` (external)
- `main._dlt_loads` (external)
- `main.daily_weather` (external)
- `main.stations` (external)
- `main._dlt_loads` (external)
- `main.daily_values` (external)
- `main.sites` (external)
- `main._dlt_loads` (external)
- `main.events` (external)

## Example query

```sql
SELECT * FROM analytics.platform_health LIMIT 100;
```
