-- Generated from soda/contracts/noaa_staging/stg_noaa_stations.yaml by scripts/generate_staging.py.
-- DO NOT EDIT by hand — run `python scripts/generate_staging.py` to regenerate.
MODEL (
  name noaa_staging.stg_noaa_stations,
  kind FULL,
  description 'Staging model for NOAA weather stations',
  grants (select_ = ['staging_reader'])
);

SELECT
    id AS station_id,
    name AS station_name,
    latitude::DOUBLE AS latitude,
    longitude::DOUBLE AS longitude,
    elevation::DOUBLE AS elevation,
    elevation_unit,
    mindate::DATE AS min_date,
    maxdate::DATE AS max_date,
    datacoverage::DOUBLE AS data_coverage,
    _location_id AS location_id,
    _loaded_at::TIMESTAMP AS loaded_at
FROM raw_noaa.main.stations
