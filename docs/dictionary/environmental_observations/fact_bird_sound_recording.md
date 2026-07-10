# environmental_observations.fact_bird_sound_recording

CDM fact: one row per Xeno-canto bird sound recording id; media remains externally linked.

## Overview

| Field | Value |
| --- | --- |
| Schema | `environmental_observations` |
| Name | `fact_bird_sound_recording` |
| Kind | `FULL` |
| Soda contract | [`soda/contracts/environmental_observations/fact_bird_sound_recording.yaml`](https://github.com/Doctacon/databox/blob/main/soda/contracts/environmental_observations/fact_bird_sound_recording.yaml) |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `also_species` | `UNKNOWN` | — | — |
| `altitude` | `UNKNOWN` | — | — |
| `animal_seen` | `UNKNOWN` | — | — |
| `audio_file_url` | `UNKNOWN` | — | — |
| `automatic_recording` | `UNKNOWN` | — | — |
| `bird_seen` | `UNKNOWN` | — | — |
| `bird_sound_recording_sk` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
| `country` | `UNKNOWN` | — | — |
| `device` | `UNKNOWN` | — | — |
| `dlt_id` | `UNKNOWN` | — | — |
| `dlt_load_id` | `UNKNOWN` | — | — |
| `english_name` | `UNKNOWN` | — | — |
| `file_name` | `UNKNOWN` | — | — |
| `genus` | `UNKNOWN` | — | — |
| `group_name` | `UNKNOWN` | — | — |
| `latitude` | `DOUBLE` | — | — |
| `length` | `UNKNOWN` | — | — |
| `license` | `UNKNOWN` | — | — |
| `loaded_at` | `TIMESTAMP` | — | — |
| `locality` | `UNKNOWN` | — | — |
| `longitude` | `DOUBLE` | — | — |
| `method` | `UNKNOWN` | — | — |
| `microphone` | `UNKNOWN` | — | — |
| `oscillogram` | `UNKNOWN` | — | — |
| `playback_used` | `UNKNOWN` | — | — |
| `quality` | `UNKNOWN` | — | — |
| `query` | `UNKNOWN` | — | — |
| `query_page` | `UNKNOWN` | — | — |
| `recording_date` | `DATE` | — | — |
| `recording_date_text` | `UNKNOWN` | — | — |
| `recording_id` | `UNKNOWN` | — | — |
| `recording_time` | `UNKNOWN` | — | — |
| `recording_type` | `UNKNOWN` | — | — |
| `recording_url` | `UNKNOWN` | — | — |
| `recordist` | `UNKNOWN` | — | — |
| `registration_number` | `UNKNOWN` | — | — |
| `remarks` | `UNKNOWN` | — | — |
| `sex` | `UNKNOWN` | — | — |
| `sonogram` | `UNKNOWN` | — | — |
| `source_id` | `UNKNOWN` | missing (must_be=0) | — |
| `source_pipeline` | `TEXT` | — | — |
| `source_url` | `UNKNOWN` | — | — |
| `species` | `UNKNOWN` | — | — |
| `species_sk` | `UNKNOWN` | missing (must_be=0) | — |
| `stage` | `UNKNOWN` | — | — |
| `subspecies` | `UNKNOWN` | — | — |
| `temperature` | `UNKNOWN` | — | — |
| `uploaded_at` | `UNKNOWN` | — | — |

## Table-level checks

- **row_count** — must_be_greater_than=0

## Lineage

**Upstream**

- [`environmental_observations.dim_species`](dim_species.md)
- `raw_xeno_canto.recordings` (external)

**Downstream**

- [`birding_agent.arizona_species_catalog`](../birding_agent/arizona_species_catalog.md)

## Example query

```sql
SELECT * FROM environmental_observations.fact_bird_sound_recording LIMIT 100;
```
