MODEL (
  name environmental_observations.fact_region_daily_stats,
  kind FULL,
  description 'CDM fact: one row per eBird region per calendar date.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

SELECT
  md5('environmental_observations|region_daily_stats|ebird_api|' || region_code || '|' || CAST(year AS VARCHAR) || '|' || CAST(month AS VARCHAR) || '|' || CAST(day AS VARCHAR)) AS region_daily_stats_sk,
  'ebird_api' AS source_pipeline,
  region_code || '|' || CAST(year AS VARCHAR) || '|' || CAST(month AS VARCHAR) || '|' || CAST(day AS VARCHAR) AS source_id,
  region_code,
  date::DATE AS stats_date,
  year,
  month,
  day,
  num_checklists,
  num_contributors,
  num_species,
  _loaded_at::TIMESTAMP AS loaded_at,
  _dlt_load_id AS dlt_load_id,
  _dlt_id AS dlt_id
FROM raw_ebird.region_stats
WHERE region_code IS NOT NULL
  AND year IS NOT NULL
  AND month IS NOT NULL
  AND day IS NOT NULL
