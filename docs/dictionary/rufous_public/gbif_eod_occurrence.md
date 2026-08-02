# rufous_public.gbif_eod_occurrence

Sanitized Arizona occurrence projection from the CC BY GBIF EOD dataset; no observer, locality, checklist, or direct-eBird fields.

## Overview

| Field | Value |
| --- | --- |
| Schema | `rufous_public` |
| Name | `gbif_eod_occurrence` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/rufous_public/gbif_eod_occurrence.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/rufous_public/gbif_eod_occurrence.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `accepted_scientific_name` | `TEXT` | — | — |
| `accepted_taxon_key` | `UNKNOWN` | — | — |
| `basis_of_record` | `TEXT` | — | — |
| `common_name` | `TEXT` | — | — |
| `coordinate_uncertainty_in_meters` | `DOUBLE` | — | — |
| `dataset_citation` | `TEXT` | — | — |
| `dataset_doi` | `TEXT` | — | — |
| `dataset_key` | `UNKNOWN` | missing (must_be=0) | — |
| `dataset_license` | `TEXT` | — | — |
| `dataset_publisher` | `TEXT` | missing (must_be=0) | — |
| `dataset_source_url` | `TEXT` | — | — |
| `dataset_title` | `TEXT` | missing (must_be=0) | — |
| `event_date` | `DATE` | missing (must_be=0) | — |
| `event_date_text` | `TEXT` | — | — |
| `family` | `TEXT` | — | — |
| `gbif_id` | `TEXT` | — | — |
| `gbif_key` | `UNKNOWN` | — | — |
| `latitude` | `DOUBLE` | missing (must_be=0) | — |
| `license` | `UNKNOWN` | missing (must_be=0) | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `longitude` | `DOUBLE` | missing (must_be=0) | — |
| `occurrence_status` | `TEXT` | — | — |
| `order_name` | `TEXT` | — | — |
| `scientific_name` | `TEXT` | missing (must_be=0) | — |
| `source_id` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `source_reference_url` | `TEXT` | — | — |
| `species_key` | `UNKNOWN` | — | — |
| `taxon_key` | `UNKNOWN` | — | — |
| `taxon_rank` | `TEXT` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_gbif.occurrences` (external)

## Example query

```sql
SELECT * FROM rufous_public.gbif_eod_occurrence LIMIT 100;
```
