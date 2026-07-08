MODEL (
  name environmental_observations.fact_weather_observation,
  kind FULL,
  description 'CDM fact: one row per NOAA station per observation date per datatype.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY station, date, datatype ORDER BY _loaded_at DESC) AS rn
  FROM raw_noaa.daily_weather
  WHERE station IS NOT NULL AND date IS NOT NULL AND datatype IS NOT NULL
)
SELECT
  md5('environmental_observations|weather_observation|noaa_api|' || station || '|' || date || '|' || datatype) AS weather_observation_sk,
  COALESCE(ws.weather_station_sk, md5('environmental_observations|weather_station|UNKNOWN')) AS weather_station_sk,
  'noaa_api' AS source_pipeline,
  station || '|' || date || '|' || datatype AS source_id,
  station AS station_id,
  date::DATE AS observation_date,
  datatype,
  value::DOUBLE AS value,
  attributes,
  source,
  _location_id AS location_id,
  _loaded_at::TIMESTAMP AS loaded_at,
  _dlt_load_id AS dlt_load_id,
  _dlt_id AS dlt_id
FROM ranked w
LEFT JOIN environmental_observations.dim_weather_station ws
  ON ws.source_pipeline = 'noaa_api' AND ws.source_id = w.station
WHERE w.rn = 1
