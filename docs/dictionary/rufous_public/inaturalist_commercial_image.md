# rufous_public.inaturalist_commercial_image

Strictly commercial-use iNaturalist taxon-photo candidates for catalog species without an approved image, selected from the latest internally coherent complete snapshot.

## Overview

| Field | Value |
| --- | --- |
| Schema | `rufous_public` |
| Name | `inaturalist_commercial_image` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/rufous_public/inaturalist_commercial_image.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/rufous_public/inaturalist_commercial_image.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `alt_text` | `TEXT` | missing (must_be=0) | — |
| `caption` | `TEXT` | missing (must_be=0) | — |
| `common_name` | `TEXT` | missing (must_be=0) | — |
| `creator` | `TEXT` | missing (must_be=0) | — |
| `discovery_method` | `TEXT` | missing (must_be=0) | — |
| `license` | `TEXT` | missing (must_be=0) | — |
| `loaded_at` | `TIMESTAMP` | missing (must_be=0) | — |
| `mime_type` | `TEXT` | missing (must_be=0) | — |
| `scientific_name` | `TEXT` | missing (must_be=0) | — |
| `source_height` | `BIGINT` | missing (must_be=0) | — |
| `source_image_url` | `TEXT` | missing (must_be=0) | — |
| `source_page_url` | `TEXT` | missing (must_be=0) | — |
| `source_published_at` | `DATE` | — | — |
| `source_width` | `BIGINT` | missing (must_be=0) | — |
| `species_code` | `TEXT` | missing (must_be=0) | — |
| `title` | `TEXT` | missing (must_be=0) | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_inaturalist.photo_candidates` (external)
- `raw_inaturalist.photo_discovery_runs` (external)
- `raw_inaturalist.photo_species_results` (external)

## Example query

```sql
SELECT * FROM rufous_public.inaturalist_commercial_image LIMIT 100;
```
