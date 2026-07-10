# birding_agent.arizona_species_catalog

One row per taxon from the single latest complete eBird US-AZ snapshot, with latest complete taxonomy, exact AVONET traits, and coherent public evidence aggregates.

## Overview

| Field | Value |
| --- | --- |
| Schema | `birding_agent` |
| Name | `arizona_species_catalog` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/birding_agent/arizona_species_catalog.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/birding_agent/arizona_species_catalog.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `arizona_species_catalog_id` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `avibase_id` | `UNKNOWN` | — | — |
| `avonet_dlt_id` | `UNKNOWN` | — | — |
| `avonet_dlt_load_id` | `UNKNOWN` | — | — |
| `avonet_family` | `UNKNOWN` | — | — |
| `avonet_loaded_at` | `UNKNOWN` | — | — |
| `avonet_order_name` | `UNKNOWN` | — | — |
| `avonet_source_url` | `UNKNOWN` | — | — |
| `beak_depth_mm` | `UNKNOWN` | — | — |
| `beak_length_culmen_mm` | `UNKNOWN` | — | — |
| `beak_length_nares_mm` | `UNKNOWN` | — | — |
| `beak_width_mm` | `UNKNOWN` | — | — |
| `bird_species_traits_sk` | `UNKNOWN` | — | — |
| `catalog_freshness_at` | `TIMESTAMP` | — | — |
| `common_name` | `UNKNOWN` | — | — |
| `complete_measures` | `UNKNOWN` | — | — |
| `dataset_doi` | `UNKNOWN` | — | — |
| `dataset_license` | `UNKNOWN` | — | — |
| `dataset_version` | `UNKNOWN` | — | — |
| `ebird_observations_loaded_at` | `UNKNOWN` | — | — |
| `extinct` | `UNKNOWN` | — | — |
| `extinct_year` | `UNKNOWN` | — | — |
| `family_code` | `UNKNOWN` | — | — |
| `family_common_name` | `UNKNOWN` | — | — |
| `family_scientific_name` | `UNKNOWN` | — | — |
| `female_individuals` | `UNKNOWN` | — | — |
| `gbif_latest_event_date` | `UNKNOWN` | — | — |
| `gbif_loaded_at` | `UNKNOWN` | — | — |
| `gbif_occurrence_count` | `BIGINT` | — | — |
| `habitat` | `UNKNOWN` | — | — |
| `habitat_density_code` | `UNKNOWN` | — | — |
| `habitat_density_label` | `UNKNOWN` | — | — |
| `hand_wing_index` | `UNKNOWN` | — | — |
| `inference` | `UNKNOWN` | — | — |
| `kipps_distance_mm` | `UNKNOWN` | — | — |
| `latest_public_observation_at` | `UNKNOWN` | — | — |
| `male_individuals` | `UNKNOWN` | — | — |
| `mass_g` | `UNKNOWN` | — | — |
| `mass_reference_other` | `UNKNOWN` | — | — |
| `mass_source` | `UNKNOWN` | — | — |
| `migration_code` | `UNKNOWN` | — | — |
| `migration_label` | `UNKNOWN` | — | — |
| `order_name` | `UNKNOWN` | — | — |
| `primary_lifestyle` | `UNKNOWN` | — | — |
| `public_location_count` | `BIGINT` | — | — |
| `recent_public_notable_count` | `BIGINT` | — | — |
| `recent_public_observation_count` | `BIGINT` | — | — |
| `reference_species` | `UNKNOWN` | — | — |
| `region_code` | `UNKNOWN` | missing (must_be=0), invalid (valid_values=['US-AZ'], must_be=0) | — |
| `report_as` | `UNKNOWN` | — | — |
| `representative_recording_id` | `UNKNOWN` | — | — |
| `representative_recording_license` | `UNKNOWN` | — | — |
| `representative_recording_quality` | `UNKNOWN` | — | — |
| `representative_recording_type` | `UNKNOWN` | — | — |
| `representative_recordist` | `UNKNOWN` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `secondary_length_mm` | `UNKNOWN` | — | — |
| `source_file_id` | `UNKNOWN` | — | — |
| `source_file_md5` | `UNKNOWN` | — | — |
| `source_scientific_name` | `UNKNOWN` | — | — |
| `species_code` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `species_list_loaded_at` | `UNKNOWN` | — | — |
| `species_natural_key` | `UNKNOWN` | — | — |
| `species_sk` | `UNKNOWN` | — | — |
| `tail_length_mm` | `UNKNOWN` | — | — |
| `tarsus_length_mm` | `UNKNOWN` | — | — |
| `taxonomic_category` | `UNKNOWN` | invalid (valid_values=['species', 'hybrid'], must_be=0) | — |
| `taxonomic_order` | `UNKNOWN` | — | — |
| `taxonomy_loaded_at` | `UNKNOWN` | — | — |
| `top_public_locations_json` | `UNKNOWN` | — | — |
| `total_individuals` | `UNKNOWN` | — | — |
| `traits_inferred` | `UNKNOWN` | — | — |
| `traits_status` | `TEXT` | missing (must_be=0), invalid (valid_values=['available', 'unavailable'], must_be=0) | — |
| `trophic_level` | `UNKNOWN` | — | — |
| `trophic_niche` | `UNKNOWN` | — | — |
| `unknown_sex_individuals` | `UNKNOWN` | — | — |
| `wing_length_mm` | `UNKNOWN` | — | — |
| `xeno_canto_latest_recording_date` | `UNKNOWN` | — | — |
| `xeno_canto_loaded_at` | `UNKNOWN` | — | — |
| `xeno_canto_recording_count` | `BIGINT` | — | — |

## Table-level checks

- **row_count** — must_be=706

## Lineage

**Upstream**

- [`environmental_observations.dim_bird_species_traits`](../environmental_observations/dim_bird_species_traits.md)
- [`environmental_observations.dim_species`](../environmental_observations/dim_species.md)
- [`environmental_observations.fact_bird_observation`](../environmental_observations/fact_bird_observation.md)
- [`environmental_observations.fact_bird_occurrence`](../environmental_observations/fact_bird_occurrence.md)
- [`environmental_observations.fact_bird_sound_recording`](../environmental_observations/fact_bird_sound_recording.md)
- `raw_ebird.species_list` (external)
- `raw_ebird.taxonomy` (external)

## Example query

```sql
SELECT * FROM birding_agent.arizona_species_catalog LIMIT 100;
```
