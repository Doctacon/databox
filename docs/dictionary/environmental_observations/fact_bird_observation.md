# environmental_observations.fact_bird_observation

CDM fact: one row per eBird observation submission id across recent and notable feeds.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `fact_bird_observation` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/fact_bird_observation.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/fact_bird_observation.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `bird_hotspot_sk` | `UNKNOWN` | missing (must_be=0) | — |
| `bird_observation_sk` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `count_display` | `TEXT` | — | — |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `exotic_category` | `UNKNOWN` | — | — |
| `is_location_private` | `UNKNOWN` | — | — |
| `is_notable` | `UNKNOWN` | — | — |
| `is_reviewed` | `UNKNOWN` | — | — |
| `is_valid` | `UNKNOWN` | — | — |
| `latitude` | `UNKNOWN` | — | — |
| `loaded_at` | `UNKNOWN` | — | — |
| `location_id` | `UNKNOWN` | — | — |
| `location_name` | `UNKNOWN` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `observation_count` | `UNKNOWN` | — | — |
| `observation_date` | `DATE` | — | — |
| `observation_datetime` | `UNKNOWN` | — | — |
| `observation_day` | `BIGINT` | — | — |
| `observation_hour` | `BIGINT` | — | — |
| `observation_month` | `BIGINT` | — | — |
| `observation_year` | `BIGINT` | — | — |
| `region_code` | `UNKNOWN` | — | — |
| `source_observation_id` | `UNKNOWN` | — | — |
| `source_pipeline` | `TEXT` | — | — |
| `source_table` | `UNKNOWN` | — | — |
| `species_code` | `UNKNOWN` | — | — |
| `species_sk` | `UNKNOWN` | missing (must_be=0) | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- [`environmental_observations.dim_bird_hotspot`](dim_bird_hotspot.md)
- [`environmental_observations.dim_species`](dim_species.md)
- `raw_ebird.notable_observations` (external)
- `raw_ebird.recent_observations` (external)

**Downstream**

- [`birding_agent.arizona_species_catalog`](../birding_agent/arizona_species_catalog.md)
- [`birding_agent.recent_observation_evidence`](../birding_agent/recent_observation_evidence.md)

## Example query

```sql
SELECT * FROM environmental_observations.fact_bird_observation LIMIT 100;
```
