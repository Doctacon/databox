# birding_agent.gbif_iceberg_occurrences

Local SQLMesh materialization of the AWS Polaris Iceberg GBIF occurrence table.

## Overview

| Field | Value |
| --- | --- |
| Schema | `birding_agent` |
| Name | `gbif_iceberg_occurrences` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/birding_agent/gbif_iceberg_occurrences.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/birding_agent/gbif_iceberg_occurrences.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `decimal_latitude` | `UNKNOWN` | — | — |
| `decimal_longitude` | `UNKNOWN` | — | — |
| `event_date` | `UNKNOWN` | — | — |
| `key` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
| `scientific_name` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_gbif.occurrences` (external)

## Example query

```sql
SELECT * FROM birding_agent.gbif_iceberg_occurrences LIMIT 100;
```
