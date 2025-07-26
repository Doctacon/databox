MODEL (
  name sqlmesh_example.stg_ebird_observations,
  kind VIEW,
  description 'Staging model for eBird bird observations'
);

SELECT
    sub_id AS submission_id,
    species_code,
    com_name AS common_name,
    sci_name AS scientific_name,
    loc_id AS location_id,
    loc_name AS location_name,
    obs_dt::timestamp AS observation_datetime,
    DATE(obs_dt::timestamp) AS observation_date,
    EXTRACT(YEAR FROM obs_dt::timestamp) AS observation_year,
    EXTRACT(MONTH FROM obs_dt::timestamp) AS observation_month,
    EXTRACT(DAY FROM obs_dt::timestamp) AS observation_day,
    EXTRACT(HOUR FROM obs_dt::timestamp) AS observation_hour,
    how_many AS count,
    CASE
        WHEN how_many IS NULL THEN 'X' -- Present but not counted
        ELSE CAST(how_many AS VARCHAR)
    END AS count_display,
    lat::DOUBLE AS latitude,
    lng::DOUBLE AS longitude,
    obs_valid AS is_valid,
    obs_reviewed AS is_reviewed,
    location_private AS is_location_private,
    _region_code AS region_code,
    FALSE AS is_notable,
    _loaded_at::timestamp AS loaded_at
FROM raw_ebird_data.recent_observations

UNION ALL

SELECT
    sub_id AS submission_id,
    species_code,
    com_name AS common_name,
    sci_name AS scientific_name,
    loc_id AS location_id,
    loc_name AS location_name,
    obs_dt::timestamp AS observation_datetime,
    DATE(obs_dt::timestamp) AS observation_date,
    EXTRACT(YEAR FROM obs_dt::timestamp) AS observation_year,
    EXTRACT(MONTH FROM obs_dt::timestamp) AS observation_month,
    EXTRACT(DAY FROM obs_dt::timestamp) AS observation_day,
    EXTRACT(HOUR FROM obs_dt::timestamp) AS observation_hour,
    how_many AS count,
    CASE
        WHEN how_many IS NULL THEN 'X' -- Present but not counted
        ELSE CAST(how_many AS VARCHAR)
    END AS count_display,
    lat::DOUBLE AS latitude,
    lng::DOUBLE AS longitude,
    obs_valid AS is_valid,
    obs_reviewed AS is_reviewed,
    location_private AS is_location_private,
    _region_code AS region_code,
    TRUE AS is_notable,
    _loaded_at::timestamp AS loaded_at
FROM raw_ebird_data.notable_observations
