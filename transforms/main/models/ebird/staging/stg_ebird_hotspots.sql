-- Generated from soda/contracts/ebird_staging/stg_ebird_hotspots.yaml by scripts/generate_staging.py.
-- DO NOT EDIT by hand — run `task staging:generate` to regenerate.
MODEL (
  name ebird_staging.stg_ebird_hotspots,
  kind FULL,
  description 'Staging model for eBird birding hotspots',
  grants (select_ = ['staging_reader'])
);

SELECT
    loc_id AS location_id,
    loc_name AS location_name,
    country_code,
    subnational1_code AS state_code,
    subnational2_code AS county_code,
    lat::DOUBLE AS latitude,
    lng::DOUBLE AS longitude,
    latest_obs_dt::TIMESTAMP AS latest_observation_datetime,
    num_species_all_time AS total_species_count,
    _region_code AS region_code,
    _loaded_at::TIMESTAMP AS loaded_at
FROM raw_ebird.main.hotspots
