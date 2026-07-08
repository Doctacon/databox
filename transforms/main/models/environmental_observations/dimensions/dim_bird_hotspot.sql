MODEL (
  name environmental_observations.dim_bird_hotspot,
  kind FULL,
  description 'CDM eBird hotspot dimension.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH ranked AS (
  SELECT
    loc_id,
    loc_name,
    country_code,
    subnational1_code,
    subnational2_code,
    _region_code AS region_code,
    lat::DOUBLE AS latitude,
    lng::DOUBLE AS longitude,
    latest_obs_dt::TIMESTAMP AS latest_observation_datetime,
    num_species_all_time,
    num_checklists_all_time,
    _loaded_at::TIMESTAMP AS loaded_at,
    ROW_NUMBER() OVER (PARTITION BY loc_id ORDER BY _loaded_at DESC) AS rn
  FROM raw_ebird.hotspots
  WHERE loc_id IS NOT NULL
)
SELECT
  md5('environmental_observations|bird_hotspot|ebird_api|' || loc_id) AS bird_hotspot_sk,
  'ebird_api' AS source_pipeline,
  loc_id AS source_id,
  loc_id AS location_id,
  loc_name AS location_name,
  country_code,
  subnational1_code,
  subnational2_code,
  region_code,
  latitude,
  longitude,
  latest_observation_datetime,
  num_species_all_time,
  num_checklists_all_time,
  loaded_at
FROM ranked
WHERE rn = 1

UNION ALL

SELECT
  md5('environmental_observations|bird_hotspot|UNKNOWN') AS bird_hotspot_sk,
  'sentinel' AS source_pipeline,
  'UNKNOWN' AS source_id,
  NULL AS location_id,
  'Unknown bird hotspot' AS location_name,
  NULL AS country_code,
  NULL AS subnational1_code,
  NULL AS subnational2_code,
  NULL AS region_code,
  NULL AS latitude,
  NULL AS longitude,
  NULL AS latest_observation_datetime,
  NULL AS num_species_all_time,
  NULL AS num_checklists_all_time,
  NULL AS loaded_at
