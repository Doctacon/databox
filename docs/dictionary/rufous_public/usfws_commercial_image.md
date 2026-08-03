# rufous_public.usfws_commercial_image

Commercial-use USFWS bird images from the latest complete caller-owned species snapshot; exact scientific tags, safe FWS URLs, usable credits, and fail-closed licenses only.

## Overview

| Field | Value |
| --- | --- |
| Schema | `rufous_public` |
| Name | `usfws_commercial_image` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/rufous_public/usfws_commercial_image.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/rufous_public/usfws_commercial_image.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `alt_text` | `TEXT` | missing (must_be=0) | — |
| `caption` | `TEXT` | — | — |
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

- `raw_usfws.image_records` (external)
- `raw_usfws.image_search_runs` (external)

## Example query

```sql
SELECT * FROM rufous_public.usfws_commercial_image LIMIT 100;
```
