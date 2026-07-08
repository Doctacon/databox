# environmental_observations.dim_species

CDM species dimension from eBird taxonomy and species list.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `dim_species` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/dim_species.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/dim_species.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `common_name` | `UNKNOWN` | — | — |
| `extinct` | `UNKNOWN` | — | — |
| `extinct_year` | `UNKNOWN` | — | — |
| `family_code` | `UNKNOWN` | — | — |
| `family_common_name` | `UNKNOWN` | — | — |
| `family_scientific_name` | `UNKNOWN` | — | — |
| `loaded_at` | `UNKNOWN` | — | — |
| `region` | `UNKNOWN` | — | — |
| `report_as` | `UNKNOWN` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `source_id` | `UNKNOWN` | — | — |
| `source_pipeline` | `UNKNOWN` | — | — |
| `species_code` | `UNKNOWN` | — | — |
| `species_sk` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `taxonomic_category` | `UNKNOWN` | — | — |
| `taxonomic_order` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_ebird.species_list` (external)
- `raw_ebird.taxonomy` (external)

**Downstream**

- [`environmental_observations.fact_bird_observation`](fact_bird_observation.md)

## Example query

```sql
SELECT * FROM environmental_observations.dim_species LIMIT 100;
```
