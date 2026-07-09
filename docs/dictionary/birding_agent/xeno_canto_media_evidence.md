# birding_agent.xeno_canto_media_evidence

Planner-ready Xeno-canto bird sound metadata with media links, license, attribution, and provenance.

## Overview

| Field | Value |
| --- | --- |
| Schema | `birding_agent` |
| Name | `xeno_canto_media_evidence` |
| Kind | `VIEW` |
| Soda contract | [`soda/contracts/birding_agent/xeno_canto_media_evidence.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/birding_agent/xeno_canto_media_evidence.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `_query` | `UNKNOWN` | — | — |
| `_query_page` | `UNKNOWN` | — | — |
| `_source_url` | `UNKNOWN` | — | — |
| `also_species` | `UNKNOWN` | — | — |
| `altitude` | `UNKNOWN` | — | — |
| `animal_seen` | `UNKNOWN` | — | — |
| `audio_file_url` | `UNKNOWN` | — | — |
| `automatic_recording` | `UNKNOWN` | — | — |
| `bird_seen` | `UNKNOWN` | — | — |
| `country` | `UNKNOWN` | — | — |
| `device` | `UNKNOWN` | — | — |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `english_name` | `UNKNOWN` | — | — |
| `evidence_source` | `TEXT` | missing (must_be=0) | — |
| `file_name` | `UNKNOWN` | — | — |
| `genus` | `UNKNOWN` | — | — |
| `group_name` | `UNKNOWN` | — | — |
| `latitude` | `UNKNOWN` | — | — |
| `length` | `UNKNOWN` | — | — |
| `license` | `UNKNOWN` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `locality` | `UNKNOWN` | — | — |
| `longitude` | `UNKNOWN` | — | — |
| `media_evidence_id` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `method` | `UNKNOWN` | — | — |
| `microphone` | `UNKNOWN` | — | — |
| `oscillogram` | `UNKNOWN` | — | — |
| `playback_used` | `UNKNOWN` | — | — |
| `quality` | `UNKNOWN` | — | — |
| `recording_date` | `UNKNOWN` | — | — |
| `recording_id` | `UNKNOWN` | — | — |
| `recording_time` | `UNKNOWN` | — | — |
| `recording_type` | `UNKNOWN` | — | — |
| `recording_url` | `UNKNOWN` | — | — |
| `recordist` | `UNKNOWN` | — | — |
| `registration_number` | `UNKNOWN` | — | — |
| `remarks` | `UNKNOWN` | — | — |
| `sex` | `UNKNOWN` | — | — |
| `sonogram` | `UNKNOWN` | — | — |
| `source_record_id` | `UNKNOWN` | missing (must_be=0) | — |
| `source_table` | `TEXT` | — | — |
| `species` | `UNKNOWN` | — | — |
| `stage` | `UNKNOWN` | — | — |
| `subspecies` | `UNKNOWN` | — | — |
| `temperature` | `UNKNOWN` | — | — |
| `uploaded_at` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- `raw_xeno_canto.recordings` (external)

## Example query

```sql
SELECT * FROM birding_agent.xeno_canto_media_evidence LIMIT 100;
```
