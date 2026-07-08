# Data dictionary

Auto-generated from SQLMesh model metadata and Soda contracts. Regenerate with `uv run python scripts/generate_docs.py`.

- **Models:** 10
- **Soda contracts:** 17
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
| [`environmental_observations.dim_species`](environmental_observations/dim_species.md) | yes | CDM species dimension from eBird taxonomy and species list. |
| [`environmental_observations.dim_streamgage_site`](environmental_observations/dim_streamgage_site.md) | yes | CDM USGS streamgage site dimension. |
| [`environmental_observations.dim_weather_station`](environmental_observations/dim_weather_station.md) | yes | CDM NOAA weather station dimension. |
| [`environmental_observations.fact_bird_observation`](environmental_observations/fact_bird_observation.md) | yes | CDM fact: one row per eBird observation submission id across recent and notable feeds. |
| [`environmental_observations.fact_earthquake_event`](environmental_observations/fact_earthquake_event.md) | yes | CDM fact: one row per USGS earthquake event id. |
| [`environmental_observations.fact_region_daily_stats`](environmental_observations/fact_region_daily_stats.md) | yes | CDM fact: one row per eBird region per calendar date. |
| [`environmental_observations.fact_streamflow_observation`](environmental_observations/fact_streamflow_observation.md) | yes | CDM fact: one row per USGS streamgage site per observation date per parameter code. |
| [`environmental_observations.fact_weather_observation`](environmental_observations/fact_weather_observation.md) | yes | CDM fact: one row per NOAA station per observation date per datatype. |
