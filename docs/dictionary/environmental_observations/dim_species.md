# environmental_observations.dim_species

Conformed CDM species dimension from eBird taxonomy, GBIF occurrence taxonomy, and Xeno-canto recording metadata.

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
| `gbif_accepted_taxon_key` | `UNKNOWN` | — | — |
| `gbif_family` | `UNKNOWN` | — | — |
| `gbif_source_id` | `UNKNOWN` | — | — |
| `gbif_taxon_key` | `UNKNOWN` | — | — |
| `gbif_taxon_rank` | `UNKNOWN` | — | — |
| `genus` | `UNKNOWN` | — | — |
| `has_gbif_occurrence` | `UNKNOWN` | — | — |
| `has_xeno_canto_recording` | `UNKNOWN` | — | — |
| `loaded_at` | `UNKNOWN` | — | — |
| `region` | `UNKNOWN` | — | — |
| `report_as` | `UNKNOWN` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `source_id` | `UNKNOWN` | — | — |
| `source_pipeline` | `UNKNOWN` | — | — |
| `species_code` | `UNKNOWN` | — | — |
| `species_natural_key` | `UNKNOWN` | — | — |
| `species_sk` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `taxonomic_category` | `UNKNOWN` | — | — |
| `taxonomic_order` | `UNKNOWN` | — | — |
| `xeno_canto_audio_file_url` | `UNKNOWN` | — | — |
| `xeno_canto_license` | `UNKNOWN` | — | — |
| `xeno_canto_quality` | `UNKNOWN` | — | — |
| `xeno_canto_recording_count` | `UNKNOWN` | — | — |
| `xeno_canto_recording_id` | `UNKNOWN` | — | — |
| `xeno_canto_recording_url` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_ebird.species_list` (external)
- `raw_ebird.taxonomy` (external)
- `raw_gbif.occurrences` (external)
- `raw_xeno_canto.recordings` (external)

**Downstream**

- [`birding_agent.arizona_species_catalog`](../birding_agent/arizona_species_catalog.md)
- [`birding_agent.gbif_occurrence_evidence`](../birding_agent/gbif_occurrence_evidence.md)
- [`birding_agent.recent_observation_evidence`](../birding_agent/recent_observation_evidence.md)
- [`birding_agent.species_lookup`](../birding_agent/species_lookup.md)
- [`environmental_observations.dim_bird_species_traits`](dim_bird_species_traits.md)
- [`environmental_observations.fact_bird_observation`](fact_bird_observation.md)
- [`environmental_observations.fact_bird_occurrence`](fact_bird_occurrence.md)
- [`environmental_observations.fact_bird_sound_recording`](fact_bird_sound_recording.md)

## Example query

```sql
SELECT * FROM environmental_observations.dim_species LIMIT 100;
```
