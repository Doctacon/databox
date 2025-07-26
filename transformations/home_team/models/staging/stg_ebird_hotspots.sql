MODEL (
  name sqlmesh_example.stg_ebird_hotspots,
  kind VIEW,
  description 'Staging model for eBird birding hotspots'
);

SELECT
    "locId" AS location_id,
    "locName" AS location_name,
    "countryCode" AS country_code,
    "subnational1Code" AS state_code,
    "subnational2Code" AS county_code,
    lat::DOUBLE AS latitude,
    lng::DOUBLE AS longitude,
    "latestObsDt"::timestamp AS latest_observation_datetime,
    "numSpeciesAllTime" AS total_species_count,
    "_region_code" AS region_code,
    "_loaded_at"::timestamp AS loaded_at
FROM raw_ebird_data.hotspots
