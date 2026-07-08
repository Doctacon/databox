MODEL (
  name environmental_observations.fact_streamflow_observation,
  kind FULL,
  description 'CDM fact: one row per USGS streamgage site per observation date per parameter code.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY site_no, observation_date, parameter_cd ORDER BY _loaded_at DESC) AS rn
  FROM raw_usgs.daily_values
  WHERE site_no IS NOT NULL AND observation_date IS NOT NULL AND parameter_cd IS NOT NULL
)
SELECT
  md5('environmental_observations|streamflow_observation|usgs_api|' || f.site_no || '|' || f.observation_date || '|' || f.parameter_cd) AS streamflow_observation_sk,
  COALESCE(ss.streamgage_site_sk, md5('environmental_observations|streamgage_site|UNKNOWN')) AS streamgage_site_sk,
  'usgs_api' AS source_pipeline,
  f.site_no || '|' || f.observation_date || '|' || f.parameter_cd AS source_id,
  f.site_no,
  f.site_name,
  f.observation_date::DATE AS observation_date,
  f.parameter_cd,
  f.parameter_name,
  f.unit_cd,
  f.value::DOUBLE AS value,
  f.qualifier,
  f._state_cd AS state_cd,
  f.latitude::DOUBLE AS latitude,
  f.longitude::DOUBLE AS longitude,
  f._loaded_at::TIMESTAMP AS loaded_at,
  f._dlt_load_id AS dlt_load_id,
  f._dlt_id AS dlt_id
FROM ranked f
LEFT JOIN environmental_observations.dim_streamgage_site ss
  ON ss.source_pipeline = 'usgs_api' AND ss.source_id = f.site_no
WHERE f.rn = 1
