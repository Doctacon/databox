# Analytics examples

Example queries against the CDM fact layer, especially
`environmental_observations.fact_bird_observation`.

## Daily species richness

```sql
SELECT
  observation_date,
  COUNT(DISTINCT species_code) AS species_richness,
  COUNT(*) AS observation_rows,
  SUM(COALESCE(observation_count, 0)) AS observed_birds
FROM environmental_observations.fact_bird_observation
GROUP BY observation_date
ORDER BY observation_date;
```

## Notable observations by species

```sql
SELECT
  s.common_name,
  s.scientific_name,
  COUNT(*) AS notable_observation_rows
FROM environmental_observations.fact_bird_observation f
JOIN environmental_observations.dim_species s
  ON s.species_sk = f.species_sk
WHERE f.is_notable
GROUP BY s.common_name, s.scientific_name
ORDER BY notable_observation_rows DESC;
```

## Weather observations by station and datatype

```sql
SELECT
  w.observation_date,
  st.station_name,
  w.datatype,
  AVG(w.value) AS avg_value
FROM environmental_observations.fact_weather_observation w
JOIN environmental_observations.dim_weather_station st
  ON st.weather_station_sk = w.weather_station_sk
GROUP BY w.observation_date, st.station_name, w.datatype
ORDER BY w.observation_date, st.station_name, w.datatype;
```

## Streamflow observations by site

```sql
SELECT
  f.observation_date,
  s.site_name,
  f.parameter_cd,
  AVG(f.value) AS avg_value
FROM environmental_observations.fact_streamflow_observation f
JOIN environmental_observations.dim_streamgage_site s
  ON s.streamgage_site_sk = f.streamgage_site_sk
GROUP BY f.observation_date, s.site_name, f.parameter_cd
ORDER BY f.observation_date, s.site_name, f.parameter_cd;
```

## Earthquake events by day

```sql
SELECT
  DATE(event_time) AS event_date,
  COUNT(*) AS events,
  MAX(magnitude) AS max_magnitude
FROM environmental_observations.fact_earthquake_event
GROUP BY event_date
ORDER BY event_date;
```
