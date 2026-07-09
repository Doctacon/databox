# birding_agent.recent_observation_evidence

Planner-ready recent eBird observation evidence from the environmental observations CDM.

## Overview

| Field | Value |
| --- | --- |
| Schema | `birding_agent` |
| Name | `recent_observation_evidence` |
| Kind | `VIEW` |
| Soda contract | [`soda/contracts/birding_agent/recent_observation_evidence.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/birding_agent/recent_observation_evidence.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `common_name` | `UNKNOWN` | — | — |
| `count_display` | `TEXT` | — | — |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `evidence_source` | `TEXT` | missing (must_be=0) | — |
| `exotic_category` | `UNKNOWN` | — | — |
| `hotspot_checklists_all_time` | `UNKNOWN` | — | — |
| `hotspot_species_all_time` | `UNKNOWN` | — | — |
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
| `observation_evidence_id` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `raw_source_table` | `UNKNOWN` | — | — |
| `region_code` | `UNKNOWN` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `source_record_id` | `UNKNOWN` | missing (must_be=0) | — |
| `source_table` | `TEXT` | — | — |
| `species_code` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- [`environmental_observations.dim_bird_hotspot`](../environmental_observations/dim_bird_hotspot.md)
- [`environmental_observations.dim_species`](../environmental_observations/dim_species.md)
- [`environmental_observations.fact_bird_observation`](../environmental_observations/fact_bird_observation.md)

## Example query

```sql
SELECT * FROM birding_agent.recent_observation_evidence LIMIT 100;
```
