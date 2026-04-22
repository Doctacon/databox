# Lineage

Full model dependency graph across all SQLMesh projects. Each node links to its data-dictionary page.

```mermaid
graph LR
    n0["analytics.fct_bird_weather_daily"]
    n1["analytics.fct_species_environment_daily"]
    n2["analytics.fct_species_weather_preferences"]
    n3["analytics.platform_health"]
    n4["ebird.dim_species"]
    n5["ebird.fct_daily_bird_observations"]
    n6["ebird.fct_hotspot_species_diversity"]
    n7["ebird.int_ebird_enriched_observations"]
    n8["ebird.int_observations_by_h3_day"]
    n9["ebird_staging.stg_ebird_hotspots"]
    n10["ebird_staging.stg_ebird_observations"]
    n11["ebird_staging.stg_ebird_taxonomy"]
    n12["noaa.fct_daily_weather"]
    n13["noaa.int_weather_by_h3_day"]
    n14["noaa_staging.stg_noaa_daily_weather"]
    n15["noaa_staging.stg_noaa_stations"]
    n16["usgs.fct_daily_streamflow"]
    n17["usgs.int_streamflow_by_h3_day"]
    n18["usgs_earthquakes.fct_daily_earthquakes"]
    n19["usgs_earthquakes_staging.stg_usgs_earthquakes_events"]
    n20["usgs_staging.stg_usgs_daily_values"]
    n21["usgs_staging.stg_usgs_sites"]
    n5 --> n0
    n12 --> n0
    n8 --> n1
    n13 --> n1
    n17 --> n1
    n0 --> n2
    n11 --> n4
    n7 --> n5
    n7 --> n6
    n9 --> n7
    n10 --> n7
    n11 --> n7
    n10 --> n8
    n14 --> n12
    n8 --> n13
    n12 --> n13
    n15 --> n13
    n20 --> n16
    n21 --> n16
    n8 --> n17
    n16 --> n17
    n21 --> n17
    n19 --> n18

    click n0 "analytics/fct_bird_weather_daily.md"
    click n1 "analytics/fct_species_environment_daily.md"
    click n2 "analytics/fct_species_weather_preferences.md"
    click n3 "analytics/platform_health.md"
    click n4 "ebird/dim_species.md"
    click n5 "ebird/fct_daily_bird_observations.md"
    click n6 "ebird/fct_hotspot_species_diversity.md"
    click n7 "ebird/int_ebird_enriched_observations.md"
    click n8 "ebird/int_observations_by_h3_day.md"
    click n9 "ebird_staging/stg_ebird_hotspots.md"
    click n10 "ebird_staging/stg_ebird_observations.md"
    click n11 "ebird_staging/stg_ebird_taxonomy.md"
    click n12 "noaa/fct_daily_weather.md"
    click n13 "noaa/int_weather_by_h3_day.md"
    click n14 "noaa_staging/stg_noaa_daily_weather.md"
    click n15 "noaa_staging/stg_noaa_stations.md"
    click n16 "usgs/fct_daily_streamflow.md"
    click n17 "usgs/int_streamflow_by_h3_day.md"
    click n18 "usgs_earthquakes/fct_daily_earthquakes.md"
    click n19 "usgs_earthquakes_staging/stg_usgs_earthquakes_events.md"
    click n20 "usgs_staging/stg_usgs_daily_values.md"
    click n21 "usgs_staging/stg_usgs_sites.md"
```
