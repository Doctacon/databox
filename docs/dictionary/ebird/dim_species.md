# ebird.dim_species

Species dimension from eBird taxonomy — one row per species_code

## Overview

| Field | Value |
| --- | --- |
| Schema | `ebird` |
| Name | `dim_species` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/ebird/dim_species.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/ebird/dim_species.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `common_name` | `UNKNOWN` | missing (must_be=0) | — |
| `family_common_name` | `UNKNOWN` | — | — |
| `family_scientific_name` | `UNKNOWN` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `species_code` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `taxonomic_category` | `UNKNOWN` | — | — |
| `taxonomic_order` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0
- **freshness** — column=loaded_at, threshold={'unit': 'hour', 'must_be_less_than': 25}

## Lineage

**Upstream**

- [`ebird_staging.stg_ebird_taxonomy`](../ebird_staging/stg_ebird_taxonomy.md)

## Example query

```sql
SELECT * FROM ebird.dim_species LIMIT 100;
```
