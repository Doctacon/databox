# usgs_earthquakes_staging.stg_usgs_earthquakes_events

Staging model for USGS earthquake events (rolling 24h feed)

## Overview

| Field | Value |
| --- | --- |
| Schema | `usgs_earthquakes_staging` |
| Name | `stg_usgs_earthquakes_events` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/usgs_earthquakes_staging/stg_usgs_earthquakes_events.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/usgs_earthquakes_staging/stg_usgs_earthquakes_events.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `alert` | `UNKNOWN` | — | — |
| `depth_km` | `DOUBLE` | — | — |
| `event_time` | `TIMESTAMP` | missing (must_be=0) | — |
| `event_type` | `UNKNOWN` | — | — |
| `event_updated_at` | `TIMESTAMP` | — | — |
| `id` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `latitude` | `DOUBLE` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `longitude` | `DOUBLE` | — | — |
| `magnitude` | `DOUBLE` | — | — |
| `magnitude_type` | `UNKNOWN` | — | — |
| `place` | `UNKNOWN` | — | — |
| `significance` | `BIGINT` | — | — |
| `status` | `UNKNOWN` | — | — |
| `title` | `UNKNOWN` | — | — |
| `tsunami_flag` | `BIGINT` | — | — |
| `url` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=loaded_at, threshold={'unit': 'hour', 'must_be_less_than': 36}

## Lineage

**Upstream**

- `main.events` (external)

**Downstream**

- [`usgs_earthquakes.fct_daily_earthquakes`](../usgs_earthquakes/fct_daily_earthquakes.md)

## Example query

```sql
SELECT * FROM usgs_earthquakes_staging.stg_usgs_earthquakes_events LIMIT 100;
```
