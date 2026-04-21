# ebird.int_observations_by_h3_day

eBird observations rolled up to H3 cell x species x observation_date. H3 resolution 6 (~36 km^2 hex). Feeds analytics.fct_species_environment_daily.

## Overview

| Field | Value |
| --- | --- |
| Schema | `ebird` |
| Name | `int_observations_by_h3_day` |
| Kind | `FULL` |
| Soda contract | _none_ |

## Columns

| Column | Type | Checks | Notes |
| --- | --- | --- | --- |
| `common_name` | `UNKNOWN` | — | — |
| `h3_cell` | `UNKNOWN` | — | — |
| `last_loaded_at` | `UNKNOWN` | — | — |
| `n_checklists` | `BIGINT` | — | — |
| `n_notable_observations` | `BIGINT` | — | — |
| `n_observations` | `BIGINT` | — | — |
| `observation_date` | `UNKNOWN` | — | — |
| `scientific_name` | `UNKNOWN` | — | — |
| `species_code` | `UNKNOWN` | — | — |
| `total_birds_counted` | `UNKNOWN` | — | — |

## Lineage

**Upstream**

- [`ebird_staging.stg_ebird_observations`](../ebird_staging/stg_ebird_observations.md)

**Downstream**

- [`analytics.fct_species_environment_daily`](../analytics/fct_species_environment_daily.md)
- [`noaa.int_weather_by_h3_day`](../noaa/int_weather_by_h3_day.md)
- [`usgs.int_streamflow_by_h3_day`](../usgs/int_streamflow_by_h3_day.md)

## Example query

```sql
SELECT * FROM ebird.int_observations_by_h3_day LIMIT 100;
```
