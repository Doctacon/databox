# rufous_public.avonet_species_traits

Commercially reusable AVONET v7 morphology and ecology projection for exact scientific-name matching; geographical range fields are not included.

## Overview

| Field | Value |
| --- | --- |
| Schema | `rufous_public` |
| Name | `avonet_species_traits` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/rufous_public/avonet_species_traits.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/rufous_public/avonet_species_traits.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `avibase_id` | `UNKNOWN` | missing (must_be=0) | — |
| `beak_depth_mm` | `UNKNOWN` | — | — |
| `beak_length_culmen_mm` | `UNKNOWN` | — | — |
| `beak_length_nares_mm` | `UNKNOWN` | — | — |
| `beak_width_mm` | `UNKNOWN` | — | — |
| `complete_measures` | `UNKNOWN` | missing (must_be=0) | — |
| `dataset_doi` | `UNKNOWN` | missing (must_be=0), invalid (valid_values=['10.6084/m9.figshare.16586228.v7'], must_be=0) | — |
| `dataset_license` | `UNKNOWN` | missing (must_be=0), invalid (valid_values=['CC BY 4.0'], must_be=0) | — |
| `dataset_version` | `UNKNOWN` | missing (must_be=0), invalid (valid_values=['v7'], must_be=0) | — |
| `family` | `UNKNOWN` | missing (must_be=0) | — |
| `female_individuals` | `UNKNOWN` | missing (must_be=0) | — |
| `habitat` | `UNKNOWN` | — | — |
| `habitat_density_code` | `UNKNOWN` | missing (must_be=0), invalid (valid_values=[1, 2, 3], must_be=0) | — |
| `habitat_density_label` | `UNKNOWN` | — | — |
| `hand_wing_index` | `UNKNOWN` | — | — |
| `inference` | `UNKNOWN` | missing (must_be=0) | — |
| `kipps_distance_mm` | `UNKNOWN` | — | — |
| `loaded_at` | `UNKNOWN` | missing (must_be=0) | — |
| `male_individuals` | `UNKNOWN` | missing (must_be=0) | — |
| `mass_g` | `UNKNOWN` | — | — |
| `mass_reference_other` | `UNKNOWN` | — | — |
| `mass_source` | `UNKNOWN` | — | — |
| `migration_code` | `UNKNOWN` | invalid (valid_values=[1, 2, 3], must_be=0) | — |
| `migration_label` | `UNKNOWN` | — | — |
| `order_name` | `UNKNOWN` | missing (must_be=0) | — |
| `primary_lifestyle` | `UNKNOWN` | — | — |
| `reference_species` | `UNKNOWN` | — | — |
| `secondary_length_mm` | `UNKNOWN` | — | — |
| `source_file_id` | `UNKNOWN` | missing (must_be=0), invalid (valid_values=[34480856], must_be=0) | — |
| `source_file_md5` | `UNKNOWN` | missing (must_be=0), invalid (valid_values=['1445afdcfb6df784010c2ca034544bc8'], must_be=0) | — |
| `source_scientific_name` | `UNKNOWN` | missing (must_be=0) | — |
| `source_url` | `UNKNOWN` | missing (must_be=0), invalid (valid_values=['https://ndownloader.figshare.com/files/34480856'], must_be=0) | — |
| `species_natural_key` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `tail_length_mm` | `UNKNOWN` | — | — |
| `tarsus_length_mm` | `UNKNOWN` | — | — |
| `total_individuals` | `UNKNOWN` | missing (must_be=0) | — |
| `traits_inferred` | `UNKNOWN` | — | — |
| `trophic_level` | `UNKNOWN` | — | — |
| `trophic_niche` | `UNKNOWN` | — | — |
| `unknown_sex_individuals` | `UNKNOWN` | missing (must_be=0) | — |
| `wing_length_mm` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_avonet.species_traits` (external)

## Example query

```sql
SELECT * FROM rufous_public.avonet_species_traits LIMIT 100;
```
