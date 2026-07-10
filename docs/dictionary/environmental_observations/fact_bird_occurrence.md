# environmental_observations.fact_bird_occurrence

CDM fact: one row per GBIF bird occurrence key.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `fact_bird_occurrence` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/fact_bird_occurrence.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/fact_bird_occurrence.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `accepted_scientific_name` | `UNKNOWN` | — | — |
| `accepted_taxon_key` | `UNKNOWN` | — | — |
| `basis_of_record` | `UNKNOWN` | — | — |
| `bird_occurrence_sk` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `catalog_number` | `UNKNOWN` | — | — |
| `class_key` | `UNKNOWN` | — | — |
| `class_name` | `UNKNOWN` | — | — |
| `collection_code` | `UNKNOWN` | — | — |
| `common_name` | `UNKNOWN` | — | — |
| `coordinate_uncertainty_in_meters` | `DOUBLE` | — | — |
| `country` | `UNKNOWN` | — | — |
| `country_code` | `UNKNOWN` | — | — |
| `dataset_key` | `UNKNOWN` | — | — |
| `day` | `BIGINT` | — | — |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `establishment_means` | `UNKNOWN` | — | — |
| `event_date` | `DATE` | — | — |
| `event_date_text` | `UNKNOWN` | — | — |
| `family` | `UNKNOWN` | — | — |
| `family_key` | `UNKNOWN` | — | — |
| `gbif_id` | `UNKNOWN` | — | — |
| `gbif_key` | `UNKNOWN` | — | — |
| `generic_name` | `UNKNOWN` | — | — |
| `genus` | `UNKNOWN` | — | — |
| `genus_key` | `UNKNOWN` | — | — |
| `hosting_organization_key` | `UNKNOWN` | — | — |
| `identified_by` | `UNKNOWN` | — | — |
| `installation_key` | `UNKNOWN` | — | — |
| `institution_code` | `UNKNOWN` | — | — |
| `kingdom` | `UNKNOWN` | — | — |
| `kingdom_key` | `UNKNOWN` | — | — |
| `last_crawled` | `UNKNOWN` | — | — |
| `last_interpreted` | `UNKNOWN` | — | — |
| `last_parsed` | `UNKNOWN` | — | — |
| `latitude` | `DOUBLE` | — | — |
| `license` | `UNKNOWN` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `locality` | `UNKNOWN` | — | — |
| `longitude` | `DOUBLE` | — | — |
| `month` | `BIGINT` | — | — |
| `occurrence_id` | `UNKNOWN` | — | — |
| `occurrence_status` | `UNKNOWN` | — | — |
| `order_key` | `UNKNOWN` | — | — |
| `order_name` | `UNKNOWN` | — | — |
| `phylum` | `UNKNOWN` | — | — |
| `phylum_key` | `UNKNOWN` | — | — |
| `protocol` | `UNKNOWN` | — | — |
| `publishing_country` | `UNKNOWN` | — | — |
| `publishing_org_key` | `UNKNOWN` | — | — |
| `query_country_code` | `UNKNOWN` | — | — |
| `query_state_province` | `UNKNOWN` | — | — |
| `query_taxon_key` | `UNKNOWN` | — | — |
| `record_number` | `UNKNOWN` | — | — |
| `recorded_by` | `UNKNOWN` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `source_id` | `TEXT` | missing (must_be=0) | — |
| `source_pipeline` | `TEXT` | — | — |
| `source_reference_url` | `UNKNOWN` | — | — |
| `source_url` | `UNKNOWN` | — | — |
| `species` | `UNKNOWN` | — | — |
| `species_key` | `UNKNOWN` | — | — |
| `species_sk` | `UNKNOWN` | missing (must_be=0) | — |
| `specific_epithet` | `UNKNOWN` | — | — |
| `state_province` | `UNKNOWN` | — | — |
| `taxon_key` | `UNKNOWN` | — | — |
| `taxon_rank` | `UNKNOWN` | — | — |
| `year` | `BIGINT` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- [`environmental_observations.dim_species`](dim_species.md)
- `raw_gbif.occurrences` (external)

**Downstream**

- [`birding_agent.arizona_species_catalog`](../birding_agent/arizona_species_catalog.md)

## Example query

```sql
SELECT * FROM environmental_observations.fact_bird_occurrence LIMIT 100;
```
