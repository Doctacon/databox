# ebird.int_ebird_enriched_observations

Intermediate model with enriched bird observations including taxonomy and location details

## Overview

| Field | Value |
| --- | --- |
| Schema | `ebird` |
| Name | `int_ebird_enriched_observations` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/ebird/int_ebird_enriched_observations.yaml`](https://github.com/crlough/databox/blob/main/soda/contracts/ebird/int_ebird_enriched_observations.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `common_name` | `UNKNOWN` | missing (must_be=0) | — |
| `count` | `UNKNOWN` | — | — |
| `count_display` | `UNKNOWN` | — | — |
| `country_code` | `UNKNOWN` | — | — |
| `county_code` | `UNKNOWN` | — | — |
| `distance_from_hotspot_miles` | `DOUBLE` | — | — |
| `family_common_name` | `UNKNOWN` | — | — |
| `family_scientific_name` | `UNKNOWN` | — | — |
| `hotspot_latest_observation` | `TIMESTAMP` | — | — |
| `hotspot_total_species` | `UNKNOWN` | — | — |
| `is_flock` | `BOOLEAN` | — | — |
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
| `region_code` | `UNKNOWN` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `season` | `TEXT` | — | — |
| `species_code` | `UNKNOWN` | missing (must_be=0) | — |
| `state_code` | `UNKNOWN` | — | — |
| `submission_id` | `UNKNOWN` | missing (must_be=0) | — |
| `taxonomic_category` | `UNKNOWN` | — | — |
| `taxonomic_order` | `UNKNOWN` | — | — |
| `time_of_day` | `TEXT` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=loaded_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- [`ebird_staging.stg_ebird_hotspots`](../ebird_staging/stg_ebird_hotspots.md)
- [`ebird_staging.stg_ebird_observations`](../ebird_staging/stg_ebird_observations.md)
- [`ebird_staging.stg_ebird_taxonomy`](../ebird_staging/stg_ebird_taxonomy.md)

**Downstream**

- [`ebird.fct_daily_bird_observations`](fct_daily_bird_observations.md)
- [`ebird.fct_hotspot_species_diversity`](fct_hotspot_species_diversity.md)

## Example query

```sql
SELECT * FROM ebird.int_ebird_enriched_observations LIMIT 100;
```
