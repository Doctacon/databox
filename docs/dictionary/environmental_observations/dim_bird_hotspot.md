# environmental_observations.dim_bird_hotspot

CDM eBird hotspot dimension.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `dim_bird_hotspot` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/dim_bird_hotspot.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/dim_bird_hotspot.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `bird_hotspot_sk` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `country_code` | `UNKNOWN` | — | — |
| `latest_observation_datetime` | `UNKNOWN` | — | — |
| `latitude` | `UNKNOWN` | — | — |
| `loaded_at` | `UNKNOWN` | — | — |
| `location_id` | `UNKNOWN` | — | — |
| `location_name` | `UNKNOWN` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `num_checklists_all_time` | `UNKNOWN` | — | — |
| `num_species_all_time` | `UNKNOWN` | — | — |
| `region_code` | `UNKNOWN` | — | — |
| `source_id` | `UNKNOWN` | — | — |
| `source_pipeline` | `UNKNOWN` | — | — |
| `subnational1_code` | `UNKNOWN` | — | — |
| `subnational2_code` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_ebird.hotspots` (external)

**Downstream**

- [`birding_agent.recent_observation_evidence`](../birding_agent/recent_observation_evidence.md)
- [`environmental_observations.fact_bird_observation`](fact_bird_observation.md)

## Example query

```sql
SELECT * FROM environmental_observations.dim_bird_hotspot LIMIT 100;
```
