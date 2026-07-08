# Lineage

Full model dependency graph across all SQLMesh projects. Each node links to its data-dictionary page.

```mermaid
graph LR
    n0["analytics.platform_health"]
    n1["environmental_observations.dim_bird_hotspot"]
    n2["environmental_observations.dim_species"]
    n3["environmental_observations.dim_streamgage_site"]
    n4["environmental_observations.dim_weather_station"]
    n5["environmental_observations.fact_bird_observation"]
    n6["environmental_observations.fact_earthquake_event"]
    n7["environmental_observations.fact_region_daily_stats"]
    n8["environmental_observations.fact_streamflow_observation"]
    n9["environmental_observations.fact_weather_observation"]
    n1 --> n5
    n2 --> n5
    n3 --> n8
    n4 --> n9

    click n0 "analytics/platform_health.md"
    click n1 "environmental_observations/dim_bird_hotspot.md"
    click n2 "environmental_observations/dim_species.md"
    click n3 "environmental_observations/dim_streamgage_site.md"
    click n4 "environmental_observations/dim_weather_station.md"
    click n5 "environmental_observations/fact_bird_observation.md"
    click n6 "environmental_observations/fact_earthquake_event.md"
    click n7 "environmental_observations/fact_region_daily_stats.md"
    click n8 "environmental_observations/fact_streamflow_observation.md"
    click n9 "environmental_observations/fact_weather_observation.md"
```
