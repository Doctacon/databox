# environmental_observations.fact_earthquake_event

CDM fact: one row per USGS earthquake event id.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `fact_earthquake_event` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/fact_earthquake_event.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/fact_earthquake_event.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `alert` | `UNKNOWN` | — | — |
| `depth_km` | `DOUBLE` | — | — |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `earthquake_event_sk` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `event_id` | `UNKNOWN` | — | — |
| `event_time` | `TIMESTAMP` | — | — |
| `event_type` | `UNKNOWN` | — | — |
| `event_updated_at` | `TIMESTAMP` | — | — |
| `latitude` | `DOUBLE` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `longitude` | `DOUBLE` | — | — |
| `magnitude` | `DOUBLE` | — | — |
| `magnitude_type` | `UNKNOWN` | — | — |
| `place` | `UNKNOWN` | — | — |
| `significance` | `BIGINT` | — | — |
| `source_id` | `UNKNOWN` | — | — |
| `source_pipeline` | `TEXT` | — | — |
| `status` | `UNKNOWN` | — | — |
| `title` | `UNKNOWN` | — | — |
| `tsunami_flag` | `BIGINT` | — | — |
| `url` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_usgs_earthquakes.events` (external)

## Example query

```sql
SELECT * FROM environmental_observations.fact_earthquake_event LIMIT 100;
```
