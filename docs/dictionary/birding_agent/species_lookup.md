# birding_agent.species_lookup

Planner-ready bird species lookup from eBird CDM species plus GBIF occurrence taxonomy fields.

## Overview

| Field | Value |
| --- | --- |
| Schema | `birding_agent` |
| Name | `species_lookup` |
| Kind | `VIEW` |
| Soda contract | [`soda/contracts/birding_agent/species_lookup.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/birding_agent/species_lookup.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `accepted_taxon_key` | `UNKNOWN` | — | — |
| `common_name` | `UNKNOWN` | — | — |
| `evidence_source` | `UNKNOWN` | missing (must_be=0) | — |
| `family_name` | `UNKNOWN` | — | — |
| `genus` | `UNKNOWN` | — | — |
| `loaded_at` | `UNKNOWN` | — | — |
| `region_code` | `UNKNOWN` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `source_record_id` | `UNKNOWN` | missing (must_be=0) | — |
| `source_table` | `UNKNOWN` | — | — |
| `species_code` | `UNKNOWN` | — | — |
| `species_lookup_id` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `taxon_key` | `UNKNOWN` | — | — |
| `taxon_rank` | `UNKNOWN` | — | — |
| `taxonomic_category` | `UNKNOWN` | — | — |
| `taxonomic_order` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- [`environmental_observations.dim_species`](../environmental_observations/dim_species.md)
- `raw_gbif.occurrences` (external)

## Example query

```sql
SELECT * FROM birding_agent.species_lookup LIMIT 100;
```
