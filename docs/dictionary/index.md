# Data dictionary

Auto-generated from SQLMesh model metadata and Soda contracts. Regenerate with `uv run python scripts/platform/generate_docs.py`.

- **Models:** 13
- **Soda contracts:** 20
- **Lineage:** [browse the dependency graph](lineage.md)

## `analytics`

Operational analytics models retained outside the CDM, such as platform health.

| Model | Contract | Description |
| --- | --- | --- |
| [`analytics.platform_health`](analytics/platform_health.md) | yes | Per-source load observability — most recent dlt load id, completion time, status, and row volume |

## `environmental_observations`

Canonical environmental-observations CDM models generated from the .schema workflow.

| Model | Contract | Description |
| --- | --- | --- |
| [`environmental_observations.dim_bird_hotspot`](environmental_observations/dim_bird_hotspot.md) | yes | CDM eBird hotspot dimension. |
| [`environmental_observations.dim_bird_species_traits`](environmental_observations/dim_bird_species_traits.md) | yes | Exact scientific-name-conformed AVONET v7 species-average bird traits with measurement and dataset provenance. |
| [`environmental_observations.dim_species`](environmental_observations/dim_species.md) | yes | Conformed CDM species dimension from eBird taxonomy, GBIF occurrence taxonomy, and Xeno-canto recording metadata. |
| [`environmental_observations.dim_streamgage_site`](environmental_observations/dim_streamgage_site.md) | yes | CDM USGS streamgage site dimension. |
| [`environmental_observations.dim_weather_station`](environmental_observations/dim_weather_station.md) | yes | CDM NOAA weather station dimension. |
| [`environmental_observations.fact_bird_observation`](environmental_observations/fact_bird_observation.md) | yes | CDM fact: one row per eBird checklist submission and species across recent and notable feeds. |
| [`environmental_observations.fact_bird_occurrence`](environmental_observations/fact_bird_occurrence.md) | yes | CDM fact: one row per GBIF bird occurrence key. |
| [`environmental_observations.fact_bird_sound_recording`](environmental_observations/fact_bird_sound_recording.md) | yes | CDM fact: one row per Xeno-canto bird sound recording id; media remains externally linked. |
| [`environmental_observations.fact_earthquake_event`](environmental_observations/fact_earthquake_event.md) | yes | CDM fact: one row per USGS earthquake event id. |
| [`environmental_observations.fact_region_daily_stats`](environmental_observations/fact_region_daily_stats.md) | yes | CDM fact: one row per eBird region per calendar date. |
| [`environmental_observations.fact_streamflow_observation`](environmental_observations/fact_streamflow_observation.md) | yes | CDM fact: one row per USGS streamgage site per observation date per parameter code. |
| [`environmental_observations.fact_weather_observation`](environmental_observations/fact_weather_observation.md) | yes | CDM fact: one row per NOAA station per observation date per datatype. |
