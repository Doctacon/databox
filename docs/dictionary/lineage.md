# Lineage

Full model dependency graph across all SQLMesh projects. Each node links to its data-dictionary page.

```mermaid
graph LR
    n0["analytics.platform_health"]
    n1["birding_agent.arizona_species_catalog"]
    n2["birding_agent.gbif_iceberg_occurrences"]
    n3["birding_agent.gbif_occurrence_evidence"]
    n4["birding_agent.recent_observation_evidence"]
    n5["birding_agent.species_lookup"]
    n6["birding_agent.xeno_canto_media_evidence"]
    n7["environmental_observations.dim_bird_hotspot"]
    n8["environmental_observations.dim_bird_species_traits"]
    n9["environmental_observations.dim_species"]
    n10["environmental_observations.dim_streamgage_site"]
    n11["environmental_observations.dim_weather_station"]
    n12["environmental_observations.fact_bird_observation"]
    n13["environmental_observations.fact_bird_occurrence"]
    n14["environmental_observations.fact_bird_sound_recording"]
    n15["environmental_observations.fact_earthquake_event"]
    n16["environmental_observations.fact_region_daily_stats"]
    n17["environmental_observations.fact_streamflow_observation"]
    n18["environmental_observations.fact_weather_observation"]
    n19["rufous_public.avonet_species_traits"]
    n20["rufous_public.gbif_eod_occurrence"]
    n21["rufous_public.inaturalist_commercial_image"]
    n22["rufous_public.usfws_commercial_image"]
    n8 --> n1
    n9 --> n1
    n12 --> n1
    n13 --> n1
    n14 --> n1
    n9 --> n3
    n7 --> n4
    n9 --> n4
    n12 --> n4
    n9 --> n5
    n9 --> n8
    n7 --> n12
    n9 --> n12
    n9 --> n13
    n9 --> n14
    n10 --> n17
    n11 --> n18

    click n0 "analytics/platform_health.md"
    click n1 "birding_agent/arizona_species_catalog.md"
    click n2 "birding_agent/gbif_iceberg_occurrences.md"
    click n3 "birding_agent/gbif_occurrence_evidence.md"
    click n4 "birding_agent/recent_observation_evidence.md"
    click n5 "birding_agent/species_lookup.md"
    click n6 "birding_agent/xeno_canto_media_evidence.md"
    click n7 "environmental_observations/dim_bird_hotspot.md"
    click n8 "environmental_observations/dim_bird_species_traits.md"
    click n9 "environmental_observations/dim_species.md"
    click n10 "environmental_observations/dim_streamgage_site.md"
    click n11 "environmental_observations/dim_weather_station.md"
    click n12 "environmental_observations/fact_bird_observation.md"
    click n13 "environmental_observations/fact_bird_occurrence.md"
    click n14 "environmental_observations/fact_bird_sound_recording.md"
    click n15 "environmental_observations/fact_earthquake_event.md"
    click n16 "environmental_observations/fact_region_daily_stats.md"
    click n17 "environmental_observations/fact_streamflow_observation.md"
    click n18 "environmental_observations/fact_weather_observation.md"
    click n19 "rufous_public/avonet_species_traits.md"
    click n20 "rufous_public/gbif_eod_occurrence.md"
    click n21 "rufous_public/inaturalist_commercial_image.md"
    click n22 "rufous_public/usfws_commercial_image.md"
```
