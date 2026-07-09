# Lineage

Full model dependency graph across all SQLMesh projects. Each node links to its data-dictionary page.

```mermaid
graph LR
    n0["analytics.platform_health"]
    n1["birding_agent.gbif_occurrence_evidence"]
    n2["birding_agent.recent_observation_evidence"]
    n3["birding_agent.species_lookup"]
    n4["birding_agent.xeno_canto_media_evidence"]
    n5["environmental_observations.dim_bird_hotspot"]
    n6["environmental_observations.dim_species"]
    n7["environmental_observations.dim_streamgage_site"]
    n8["environmental_observations.dim_weather_station"]
    n9["environmental_observations.fact_bird_observation"]
    n10["environmental_observations.fact_bird_occurrence"]
    n11["environmental_observations.fact_bird_sound_recording"]
    n12["environmental_observations.fact_earthquake_event"]
    n13["environmental_observations.fact_region_daily_stats"]
    n14["environmental_observations.fact_streamflow_observation"]
    n15["environmental_observations.fact_weather_observation"]
    n5 --> n2
    n6 --> n2
    n9 --> n2
    n6 --> n3
    n5 --> n9
    n6 --> n9
    n6 --> n10
    n6 --> n11
    n7 --> n14
    n8 --> n15

    click n0 "analytics/platform_health.md"
    click n1 "birding_agent/gbif_occurrence_evidence.md"
    click n2 "birding_agent/recent_observation_evidence.md"
    click n3 "birding_agent/species_lookup.md"
    click n4 "birding_agent/xeno_canto_media_evidence.md"
    click n5 "environmental_observations/dim_bird_hotspot.md"
    click n6 "environmental_observations/dim_species.md"
    click n7 "environmental_observations/dim_streamgage_site.md"
    click n8 "environmental_observations/dim_weather_station.md"
    click n9 "environmental_observations/fact_bird_observation.md"
    click n10 "environmental_observations/fact_bird_occurrence.md"
    click n11 "environmental_observations/fact_bird_sound_recording.md"
    click n12 "environmental_observations/fact_earthquake_event.md"
    click n13 "environmental_observations/fact_region_daily_stats.md"
    click n14 "environmental_observations/fact_streamflow_observation.md"
    click n15 "environmental_observations/fact_weather_observation.md"
```
