# ebird.fct_hotspot_species_diversity

Per-hotspot biodiversity metrics including Shannon diversity index and species richness

## Overview

| Field | Value |
| --- | --- |
| Schema | `ebird` |
| Name | `fct_hotspot_species_diversity` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/ebird/fct_hotspot_species_diversity.yaml`](https://github.com/crlough/databox/blob/main/soda/contracts/ebird/fct_hotspot_species_diversity.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `county_code` | `UNKNOWN` | — | — |
| `first_observation_date` | `UNKNOWN` | — | — |
| `last_loaded_at` | `UNKNOWN` | — | — |
| `last_observation_date` | `UNKNOWN` | — | — |
| `last_updated_at` | `TIMESTAMP` | — | — |
| `latitude` | `UNKNOWN` | — | — |
| `location_id` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `location_name` | `UNKNOWN` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `most_common_species_code` | `UNKNOWN` | — | — |
| `most_common_species_name` | `UNKNOWN` | — | — |
| `pct_notable_observations` | `DOUBLE` | — | — |
| `peak_season` | `TEXT` | — | — |
| `shannon_diversity_index` | `DOUBLE` | — | — |
| `state_code` | `UNKNOWN` | — | — |
| `total_observations` | `BIGINT` | missing (must_be=0) | — |
| `total_species_count` | `BIGINT` | missing (must_be=0) | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=last_updated_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- [`ebird.int_ebird_enriched_observations`](int_ebird_enriched_observations.md)

## Example query

```sql
SELECT * FROM ebird.fct_hotspot_species_diversity LIMIT 100;
```
