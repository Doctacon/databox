MODEL (
  name noaa.stg_noaa_stations,
  kind VIEW,
  description 'Staging model for NOAA weather stations'
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
FROM raw_noaa.stations
