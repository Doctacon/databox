-- Generated from soda/contracts/noaa_staging/stg_noaa_daily_weather.yaml by scripts/generate_staging.py.
-- DO NOT EDIT by hand — run `task staging:generate` to regenerate.
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
    value::DOUBLE AS value,
    attributes,
    source,
    _location_id AS location_id,
    _loaded_at::TIMESTAMP AS loaded_at
FROM raw_noaa.main.daily_weather
