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

- `raw_ebird._dlt_loads` (external)
- `raw_ebird.hotspots` (external)
- `raw_ebird.notable_observations` (external)
- `raw_ebird.recent_observations` (external)
- `raw_ebird.species_list` (external)
- `raw_gbif._dlt_loads` (external)
- `raw_gbif.occurrences` (external)
- `raw_noaa._dlt_loads` (external)
- `raw_noaa.daily_weather` (external)
- `raw_noaa.stations` (external)
- `raw_usgs._dlt_loads` (external)
- `raw_usgs.daily_values` (external)
- `raw_usgs.sites` (external)
- `raw_usgs_earthquakes._dlt_loads` (external)
- `raw_usgs_earthquakes.events` (external)
- `raw_xeno_canto._dlt_loads` (external)
- `raw_xeno_canto.recordings` (external)

## Example query

```sql
SELECT * FROM analytics.platform_health LIMIT 100;
```
