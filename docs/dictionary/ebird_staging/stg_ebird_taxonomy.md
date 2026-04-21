# ebird_staging.stg_ebird_taxonomy

Staging model for eBird taxonomy reference data

## Overview

| Field | Value |
| --- | --- |
| Schema | `ebird_staging` |
| Name | `stg_ebird_taxonomy` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/ebird_staging/stg_ebird_taxonomy.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/ebird_staging/stg_ebird_taxonomy.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `common_name` | `UNKNOWN` | missing (must_be=0) | — |
| `family_common_name` | `UNKNOWN` | — | — |
| `family_scientific_name` | `UNKNOWN` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `scientific_name` | `UNKNOWN` | missing (must_be=0) | — |
| `species_code` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `taxonomic_category` | `UNKNOWN` | — | — |
| `taxonomic_order` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=loaded_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- `main.taxonomy` (external)

**Downstream**

- [`ebird.dim_species`](../ebird/dim_species.md)
- [`ebird.int_ebird_enriched_observations`](../ebird/int_ebird_enriched_observations.md)

## Example query

```sql
SELECT * FROM ebird_staging.stg_ebird_taxonomy LIMIT 100;
```
