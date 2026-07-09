# birding_agent.gbif_occurrence_evidence

Planner-ready GBIF bird occurrence evidence conformed to eBird-first species names with location, license, and source provenance.

## Overview

| Field | Value |
| --- | --- |
| Schema | `birding_agent` |
| Name | `gbif_occurrence_evidence` |
| Kind | `VIEW` |
| Soda contract | [`soda/contracts/birding_agent/gbif_occurrence_evidence.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/birding_agent/gbif_occurrence_evidence.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `_query_country_code` | `UNKNOWN` | — | — |
| `_query_state_province` | `UNKNOWN` | — | — |
| `_query_taxon_key` | `UNKNOWN` | — | — |
| `_source_url` | `UNKNOWN` | — | — |
| `accepted_scientific_name` | `UNKNOWN` | — | — |
| `accepted_taxon_key` | `UNKNOWN` | — | — |
| `basis_of_record` | `UNKNOWN` | — | — |
| `common_name` | `TEXT` | — | — |
| `coordinate_uncertainty_in_meters` | `UNKNOWN` | — | — |
| `country` | `UNKNOWN` | — | — |
| `country_code` | `UNKNOWN` | — | — |
| `dataset_key` | `UNKNOWN` | — | — |
| `day` | `UNKNOWN` | — | — |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `establishment_means` | `UNKNOWN` | — | — |
| `event_date_text` | `UNKNOWN` | — | — |
| `evidence_source` | `TEXT` | missing (must_be=0) | — |
| `family` | `UNKNOWN` | — | — |
| `gbif_id` | `UNKNOWN` | — | — |
| `gbif_key` | `UNKNOWN` | — | — |
| `genus` | `UNKNOWN` | — | — |
| `last_crawled` | `UNKNOWN` | — | — |
| `last_interpreted` | `UNKNOWN` | — | — |
| `last_parsed` | `UNKNOWN` | — | — |
| `latitude` | `UNKNOWN` | — | — |
| `license` | `UNKNOWN` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `locality` | `UNKNOWN` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `month` | `UNKNOWN` | — | — |
| `occurrence_evidence_id` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `occurrence_id` | `UNKNOWN` | — | — |
| `occurrence_status` | `UNKNOWN` | — | — |
| `publishing_org_key` | `UNKNOWN` | — | — |
| `scientific_name` | `TEXT` | — | — |
| `source_record_id` | `TEXT` | missing (must_be=0) | — |
| `source_reference_url` | `UNKNOWN` | — | — |
| `source_scientific_name` | `UNKNOWN` | — | — |
| `source_table` | `TEXT` | — | — |
| `species` | `UNKNOWN` | — | — |
| `species_code` | `UNKNOWN` | — | — |
| `species_natural_key` | `UNKNOWN` | — | — |
| `state_province` | `UNKNOWN` | — | — |
| `taxon_key` | `UNKNOWN` | — | — |
| `taxon_rank` | `UNKNOWN` | — | — |
| `year` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- [`environmental_observations.dim_species`](../environmental_observations/dim_species.md)
- `raw_gbif.occurrences` (external)

## Example query

```sql
SELECT * FROM birding_agent.gbif_occurrence_evidence LIMIT 100;
```
