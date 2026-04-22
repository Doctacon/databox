# usgs_earthquakes.fct_daily_earthquakes

Daily earthquake summary — one row per UTC day, counts and magnitude stats

## Overview

| Field | Value |
| --- | --- |
| Schema | `usgs_earthquakes` |
| Name | `fct_daily_earthquakes` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/usgs_earthquakes/fct_daily_earthquakes.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/usgs_earthquakes/fct_daily_earthquakes.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `avg_magnitude` | `DOUBLE` | — | — |
| `event_count` | `BIGINT` | missing (must_be=0) | — |
| `event_date` | `DATE` | missing (must_be=0), duplicate (must_be=0) | — |
| `last_updated_at` | `TIMESTAMP` | — | — |
| `max_magnitude` | `DOUBLE` | — | — |
| `max_significance` | `BIGINT` | — | — |
| `tsunami_alert_count` | `BIGINT` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=last_updated_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- [`usgs_earthquakes_staging.stg_usgs_earthquakes_events`](../usgs_earthquakes_staging/stg_usgs_earthquakes_events.md)

## Example query

```sql
SELECT * FROM usgs_earthquakes.fct_daily_earthquakes LIMIT 100;
```
