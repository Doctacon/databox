# Data dictionary

Auto-generated from SQLMesh model metadata and Soda contracts. Regenerate with `uv run python scripts/generate_docs.py`.

- **Models:** 22
- **Soda contracts:** 26
- **Lineage:** [browse the dependency graph](lineage.md)

## `analytics`

Cross-domain marts that join bird, weather, and streamflow signals.

| Model | Contract | Description |
| --- | --- | --- |
| [`analytics.fct_bird_weather_daily`](analytics/fct_bird_weather_daily.md) | yes | eBird daily observations joined with NOAA weather conditions — one row per region x date x species |
| [`analytics.fct_species_environment_daily`](analytics/fct_species_environment_daily.md) | yes | Flagship cross-domain mart: bird observations joined to daily weather and streamflow at species x H3 cell (resolution 6, ~36 km^2) x day grain |
| [`analytics.fct_species_weather_preferences`](analytics/fct_species_weather_preferences.md) | yes | Per-species weather preference aggregates — what conditions correlate with each species appearing |
| [`analytics.platform_health`](analytics/platform_health.md) | yes | Per-source load observability — most recent dlt load id, completion time, status, and row volume |

## `ebird`

eBird bird-observation domain — intermediate and mart models.

| Model | Contract | Description |
| --- | --- | --- |
| [`ebird.dim_species`](ebird/dim_species.md) | yes | Species dimension from eBird taxonomy — one row per species_code |
| [`ebird.fct_daily_bird_observations`](ebird/fct_daily_bird_observations.md) | yes | Daily bird observation facts aggregated by region, date, and species |
| [`ebird.fct_hotspot_species_diversity`](ebird/fct_hotspot_species_diversity.md) | yes | Per-hotspot biodiversity metrics including Shannon diversity index and species richness |
| [`ebird.int_ebird_enriched_observations`](ebird/int_ebird_enriched_observations.md) | yes | Intermediate model with enriched bird observations including taxonomy and location details |
| [`ebird.int_observations_by_h3_day`](ebird/int_observations_by_h3_day.md) | — | eBird observations rolled up to H3 cell x species x observation_date |

## `ebird_staging`

eBird staging views — raw dlt loads with column renames only.

| Model | Contract | Description |
| --- | --- | --- |
| [`ebird_staging.stg_ebird_hotspots`](ebird_staging/stg_ebird_hotspots.md) | yes | Staging model for eBird birding hotspots |
| [`ebird_staging.stg_ebird_observations`](ebird_staging/stg_ebird_observations.md) | yes | Staging model for eBird bird observations |
| [`ebird_staging.stg_ebird_taxonomy`](ebird_staging/stg_ebird_taxonomy.md) | yes | Staging model for eBird taxonomy reference data |

## `noaa`

NOAA weather domain — intermediate and mart models.

| Model | Contract | Description |
| --- | --- | --- |
| [`noaa.fct_daily_weather`](noaa/fct_daily_weather.md) | yes | Daily weather facts pivoted from normalized observations to one row per station per date |
| [`noaa.int_weather_by_h3_day`](noaa/int_weather_by_h3_day.md) | — | Daily NOAA weather assigned to each H3 cell in the bird-observation universe via nearest-station join |

## `noaa_staging`

NOAA staging views — raw dlt loads with column renames only.

| Model | Contract | Description |
| --- | --- | --- |
| [`noaa_staging.stg_noaa_daily_weather`](noaa_staging/stg_noaa_daily_weather.md) | yes | Staging model for NOAA daily weather observations |
| [`noaa_staging.stg_noaa_stations`](noaa_staging/stg_noaa_stations.md) | yes | Staging model for NOAA weather stations |

## `usgs`

USGS streamflow domain — intermediate and mart models.

| Model | Contract | Description |
| --- | --- | --- |
| [`usgs.fct_daily_streamflow`](usgs/fct_daily_streamflow.md) | yes | Daily streamflow facts pivoted to one row per site per date with key hydrological metrics |
| [`usgs.int_streamflow_by_h3_day`](usgs/int_streamflow_by_h3_day.md) | — | Daily USGS streamflow assigned to each H3 cell in the bird-observation universe via nearest-gauge join |

## `usgs_earthquakes`

USGS earthquakes domain — intermediate and mart models.

| Model | Contract | Description |
| --- | --- | --- |
| [`usgs_earthquakes.fct_daily_earthquakes`](usgs_earthquakes/fct_daily_earthquakes.md) | yes | Daily earthquake summary — one row per UTC day, counts and magnitude stats |

## `usgs_earthquakes_staging`

USGS earthquakes staging views — raw dlt loads with column renames only.

| Model | Contract | Description |
| --- | --- | --- |
| [`usgs_earthquakes_staging.stg_usgs_earthquakes_events`](usgs_earthquakes_staging/stg_usgs_earthquakes_events.md) | yes | Staging model for USGS earthquake events (rolling 24h feed) |

## `usgs_staging`

USGS staging views — raw dlt loads with column renames only.

| Model | Contract | Description |
| --- | --- | --- |
| [`usgs_staging.stg_usgs_daily_values`](usgs_staging/stg_usgs_daily_values.md) | yes | Staging model for USGS daily streamflow and gage observations |
| [`usgs_staging.stg_usgs_sites`](usgs_staging/stg_usgs_sites.md) | yes | Staging model for USGS monitoring site metadata |
