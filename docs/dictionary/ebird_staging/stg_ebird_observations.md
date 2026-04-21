# ebird_staging.stg_ebird_observations

Staging model for eBird bird observations

## Overview

| Field | Value |
| --- | --- |
| Schema | `ebird_staging` |
| Name | `stg_ebird_observations` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/ebird_staging/stg_ebird_observations.yaml`](https://github.com/crlough/databox/blob/main/soda/contracts/ebird_staging/stg_ebird_observations.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `common_name` | `UNKNOWN` | missing (must_be=0) | — |
| `count` | `UNKNOWN` | — | — |
| `count_display` | `UNKNOWN` | — | — |
| `is_location_private` | `UNKNOWN` | — | — |
| `is_notable` | `UNKNOWN` | — | — |
| `is_reviewed` | `UNKNOWN` | — | — |
| `is_valid` | `UNKNOWN` | — | — |
| `latitude` | `UNKNOWN` | — | — |
| `loaded_at` | `UNKNOWN` | — | — |
| `location_id` | `UNKNOWN` | missing (must_be=0) | — |
| `location_name` | `UNKNOWN` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `observation_date` | `UNKNOWN` | missing (must_be=0) | — |
| `observation_datetime` | `UNKNOWN` | missing (must_be=0) | — |
| `observation_day` | `UNKNOWN` | — | — |
| `observation_hour` | `UNKNOWN` | — | — |
| `observation_month` | `UNKNOWN` | — | — |
| `observation_year` | `UNKNOWN` | — | — |
| `region_code` | `UNKNOWN` | missing (must_be=0) | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `species_code` | `UNKNOWN` | missing (must_be=0) | — |
| `submission_id` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=loaded_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- `main.notable_observations` (external)
- `main.recent_observations` (external)

**Downstream**

- [`ebird.int_ebird_enriched_observations`](../ebird/int_ebird_enriched_observations.md)
- [`ebird.int_observations_by_h3_day`](../ebird/int_observations_by_h3_day.md)

## Example query

```sql
SELECT * FROM ebird_staging.stg_ebird_observations LIMIT 100;
```
