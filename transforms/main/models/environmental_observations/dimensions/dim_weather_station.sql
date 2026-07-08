MODEL (
  name environmental_observations.dim_weather_station,
  kind FULL,
  description 'CDM NOAA weather station dimension.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH ranked AS (
  SELECT
    id,
    name,
    latitude::DOUBLE AS latitude,
    longitude::DOUBLE AS longitude,
    elevation::DOUBLE AS elevation,
    elevation_unit,
    mindate::DATE AS min_date,
    maxdate::DATE AS max_date,
    datacoverage::DOUBLE AS data_coverage,
    _location_id AS location_id,
    _loaded_at::TIMESTAMP AS loaded_at,
    ROW_NUMBER() OVER (PARTITION BY id ORDER BY _loaded_at DESC) AS rn
  FROM raw_noaa.stations
  WHERE id IS NOT NULL
)
SELECT
  md5('environmental_observations|weather_station|noaa_api|' || id) AS weather_station_sk,
  'noaa_api' AS source_pipeline,
  id AS source_id,
  id AS station_id,
  name AS station_name,
  latitude,
  longitude,
  elevation,
  elevation_unit,
  min_date,
  max_date,
  data_coverage,
  location_id,
  loaded_at
FROM ranked
WHERE rn = 1

UNION ALL

SELECT
  md5('environmental_observations|weather_station|UNKNOWN') AS weather_station_sk,
  'sentinel' AS source_pipeline,
  'UNKNOWN' AS source_id,
  NULL AS station_id,
  'Unknown weather station' AS station_name,
  NULL AS latitude,
  NULL AS longitude,
  NULL AS elevation,
  NULL AS elevation_unit,
  NULL AS min_date,
  NULL AS max_date,
  NULL AS data_coverage,
  NULL AS location_id,
  NULL AS loaded_at
