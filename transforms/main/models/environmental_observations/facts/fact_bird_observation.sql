MODEL (
  name environmental_observations.fact_bird_observation,
  kind FULL,
  description 'CDM fact: one row per eBird observation submission id across recent and notable feeds.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH observations AS (
  SELECT
    'recent_observations' AS source_table,
    sub_id,
    species_code,
    com_name,
    sci_name,
    loc_id,
    loc_name,
    obs_dt::TIMESTAMP AS observation_datetime,
    how_many,
    lat::DOUBLE AS latitude,
    lng::DOUBLE AS longitude,
    obs_valid,
    obs_reviewed,
    location_private,
    _region_code,
    FALSE AS is_notable,
    exotic_category,
    _loaded_at::TIMESTAMP AS loaded_at,
    _dlt_load_id,
    _dlt_id
  FROM raw_ebird.recent_observations
  WHERE sub_id IS NOT NULL

  UNION ALL

  SELECT
    'notable_observations' AS source_table,
    sub_id,
    species_code,
    com_name,
    sci_name,
    loc_id,
    loc_name,
    obs_dt::TIMESTAMP AS observation_datetime,
    how_many,
    lat::DOUBLE AS latitude,
    lng::DOUBLE AS longitude,
    obs_valid,
    obs_reviewed,
    location_private,
    _region_code,
    TRUE AS is_notable,
    exotic_category,
    _loaded_at::TIMESTAMP AS loaded_at,
    _dlt_load_id,
    _dlt_id
  FROM raw_ebird.notable_observations
  WHERE sub_id IS NOT NULL
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY sub_id ORDER BY is_notable DESC, loaded_at DESC) AS rn
  FROM observations
)
SELECT
  md5('environmental_observations|bird_observation|ebird_api|' || o.sub_id) AS bird_observation_sk,
  COALESCE(s.species_sk, md5('environmental_observations|species|UNKNOWN')) AS species_sk,
  COALESCE(h.bird_hotspot_sk, md5('environmental_observations|bird_hotspot|UNKNOWN')) AS bird_hotspot_sk,
  'ebird_api' AS source_pipeline,
  o.source_table,
  o.sub_id AS source_observation_id,
  o.observation_datetime,
  DATE(o.observation_datetime) AS observation_date,
  EXTRACT(YEAR FROM o.observation_datetime)::BIGINT AS observation_year,
  EXTRACT(MONTH FROM o.observation_datetime)::BIGINT AS observation_month,
  EXTRACT(DAY FROM o.observation_datetime)::BIGINT AS observation_day,
  EXTRACT(HOUR FROM o.observation_datetime)::BIGINT AS observation_hour,
  o.species_code,
  o.loc_id AS location_id,
  o.loc_name AS location_name,
  o._region_code AS region_code,
  o.latitude,
  o.longitude,
  o.how_many AS observation_count,
  CASE WHEN o.how_many IS NULL THEN 'X' ELSE CAST(o.how_many AS VARCHAR) END AS count_display,
  o.obs_valid AS is_valid,
  o.obs_reviewed AS is_reviewed,
  o.location_private AS is_location_private,
  o.is_notable,
  o.exotic_category,
  o.loaded_at,
  o._dlt_load_id AS dlt_load_id,
  o._dlt_id AS dlt_id
FROM ranked o
LEFT JOIN environmental_observations.dim_species s
  ON s.source_pipeline = 'ebird_api' AND s.source_id = o.species_code
LEFT JOIN environmental_observations.dim_bird_hotspot h
  ON h.source_pipeline = 'ebird_api' AND h.source_id = o.loc_id
WHERE o.rn = 1
