MODEL (
  name environmental_observations.dim_streamgage_site,
  kind FULL,
  description 'CDM USGS streamgage site dimension.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH ranked AS (
  SELECT
    site_no,
    site_name,
    site_type,
    latitude::DOUBLE AS latitude,
    longitude::DOUBLE AS longitude,
    county_cd,
    state_cd,
    huc_cd,
    drain_area_va::DOUBLE AS drainage_area_sqmi,
    begin_date::DATE AS begin_date,
    end_date::DATE AS end_date,
    _loaded_at::TIMESTAMP AS loaded_at,
    ROW_NUMBER() OVER (PARTITION BY site_no ORDER BY _loaded_at DESC) AS rn
  FROM raw_usgs.sites
  WHERE site_no IS NOT NULL
)
SELECT
  md5('environmental_observations|streamgage_site|usgs_api|' || site_no) AS streamgage_site_sk,
  'usgs_api' AS source_pipeline,
  site_no AS source_id,
  site_no,
  site_name,
  site_type,
  latitude,
  longitude,
  county_cd,
  state_cd,
  huc_cd,
  drainage_area_sqmi,
  begin_date,
  end_date,
  loaded_at
FROM ranked
WHERE rn = 1

UNION ALL

SELECT
  md5('environmental_observations|streamgage_site|UNKNOWN') AS streamgage_site_sk,
  'sentinel' AS source_pipeline,
  'UNKNOWN' AS source_id,
  NULL AS site_no,
  'Unknown streamgage site' AS site_name,
  NULL AS site_type,
  NULL AS latitude,
  NULL AS longitude,
  NULL AS county_cd,
  NULL AS state_cd,
  NULL AS huc_cd,
  NULL AS drainage_area_sqmi,
  NULL AS begin_date,
  NULL AS end_date,
  NULL AS loaded_at
