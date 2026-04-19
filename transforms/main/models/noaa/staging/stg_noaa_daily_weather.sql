MODEL (
  name noaa_staging.stg_noaa_daily_weather,
  kind FULL,
  description 'Staging model for NOAA daily weather observations',
  grants (select_ = ['staging_reader'])
);

SELECT
    date::DATE AS observation_date,
    datatype,
    station,
    CASE
        WHEN value IS NOT NULL THEN CAST(value AS DOUBLE)
        ELSE NULL
    END AS value,
    attributes,
    source,
    _location_id AS location_id,
    _loaded_at::TIMESTAMP AS loaded_at
FROM raw_noaa.main.daily_weather
