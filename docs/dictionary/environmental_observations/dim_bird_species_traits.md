# environmental_observations.dim_bird_species_traits

Exact scientific-name-conformed AVONET v7 species-average bird traits with measurement and dataset provenance.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `dim_bird_species_traits` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/dim_bird_species_traits.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/dim_bird_species_traits.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `avibase_id` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `beak_depth_mm` | `UNKNOWN` | — | — |
| `beak_length_culmen_mm` | `UNKNOWN` | — | — |
| `beak_length_nares_mm` | `UNKNOWN` | — | — |
| `beak_width_mm` | `UNKNOWN` | — | — |
| `bird_species_traits_sk` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `complete_measures` | `UNKNOWN` | — | — |
| `dataset_doi` | `UNKNOWN` | — | — |
| `dataset_license` | `UNKNOWN` | — | — |
| `dataset_version` | `UNKNOWN` | — | — |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `family` | `UNKNOWN` | — | — |
| `female_individuals` | `UNKNOWN` | — | — |
| `habitat` | `UNKNOWN` | — | — |
| `habitat_density_code` | `UNKNOWN` | invalid (valid_values=[1, 2, 3], must_be=0) | — |
| `habitat_density_label` | `UNKNOWN` | invalid (valid_values=['Dense', 'Semi-open', 'Open'], must_be=0) | — |
| `hand_wing_index` | `UNKNOWN` | — | — |
| `inference` | `UNKNOWN` | — | — |
| `kipps_distance_mm` | `UNKNOWN` | — | — |
| `loaded_at` | `UNKNOWN` | — | — |
| `male_individuals` | `UNKNOWN` | — | — |
| `mass_g` | `UNKNOWN` | — | — |
| `mass_reference_other` | `UNKNOWN` | — | — |
| `mass_source` | `UNKNOWN` | — | — |
| `migration_code` | `UNKNOWN` | — | — |
| `migration_label` | `UNKNOWN` | — | — |
| `order_name` | `UNKNOWN` | — | — |
| `primary_lifestyle` | `UNKNOWN` | — | — |
| `reference_species` | `UNKNOWN` | — | — |
| `secondary_length_mm` | `UNKNOWN` | — | — |
| `source_file_id` | `UNKNOWN` | — | — |
| `source_file_md5` | `UNKNOWN` | — | — |
| `source_scientific_name` | `UNKNOWN` | — | — |
| `source_url` | `UNKNOWN` | — | — |
| `species_natural_key` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `species_sk` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `tail_length_mm` | `UNKNOWN` | — | — |
| `tarsus_length_mm` | `UNKNOWN` | — | — |
| `total_individuals` | `UNKNOWN` | — | — |
| `traits_inferred` | `UNKNOWN` | — | — |
| `trophic_level` | `UNKNOWN` | — | — |
| `trophic_niche` | `UNKNOWN` | — | — |
| `unknown_sex_individuals` | `UNKNOWN` | — | — |
| `wing_length_mm` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- [`environmental_observations.dim_species`](dim_species.md)
- `raw_avonet.species_traits` (external)

**Downstream**

- [`birding_agent.arizona_species_catalog`](../birding_agent/arizona_species_catalog.md)

## Example query

```sql
SELECT * FROM environmental_observations.dim_bird_species_traits LIMIT 100;
```
