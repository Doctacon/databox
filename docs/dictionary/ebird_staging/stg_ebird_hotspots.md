# ebird_staging.stg_ebird_hotspots

Staging model for eBird birding hotspots

## Overview

| Field | Value |
| --- | --- |
| Schema | `ebird_staging` |
| Name | `stg_ebird_hotspots` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/ebird_staging/stg_ebird_hotspots.yaml`](https://github.com/crlough/databox/blob/main/soda/contracts/ebird_staging/stg_ebird_hotspots.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `country_code` | `UNKNOWN` | — | — |
| `county_code` | `UNKNOWN` | — | — |
| `latest_observation_datetime` | `TIMESTAMP` | — | — |
| `latitude` | `DOUBLE` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `location_id` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `location_name` | `UNKNOWN` | missing (must_be=0) | — |
| `longitude` | `DOUBLE` | — | — |
| `region_code` | `UNKNOWN` | — | — |
| `state_code` | `UNKNOWN` | — | — |
| `total_species_count` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=loaded_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- `main.hotspots` (external)

**Downstream**

- [`ebird.int_ebird_enriched_observations`](../ebird/int_ebird_enriched_observations.md)

## Example query

```sql
SELECT * FROM ebird_staging.stg_ebird_hotspots LIMIT 100;
```
