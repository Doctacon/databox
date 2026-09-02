-- platform-health-codegen: generated — edit packages/databox/databox/quality/platform_health_codegen.py
MODEL (
  name analytics.platform_health,
  kind VIEW,
  description 'Per-source load observability — most recent dlt load id, completion time, status, and row volume. One row per source.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH ebird_loads AS (
  SELECT
    'ebird'             AS source,
    load_id,
    schema_name,
    status,
    inserted_at::TIMESTAMP AS completed_at
  FROM polaris_aws.raw_ebird._dlt_load_status
),
gbif_loads AS (
  SELECT
    'gbif'             AS source,
    load_id,
    schema_name,
    status,
    inserted_at::TIMESTAMP AS completed_at
  FROM polaris_aws.raw_gbif._dlt_load_status
),
avonet_loads AS (
  SELECT
    'avonet'             AS source,
    load_id,
    schema_name,
    status,
    inserted_at::TIMESTAMP AS completed_at
  FROM polaris_aws.raw_avonet._dlt_load_status
),
xeno_canto_loads AS (
  SELECT
    'xeno_canto'             AS source,
    load_id,
    schema_name,
    status,
    inserted_at::TIMESTAMP AS completed_at
  FROM polaris_aws.raw_xeno_canto._dlt_load_status
),
noaa_loads AS (
  SELECT
    'noaa'             AS source,
    load_id,
    schema_name,
    status,
    inserted_at::TIMESTAMP AS completed_at
  FROM polaris_aws.raw_noaa._dlt_load_status
),
usgs_loads AS (
  SELECT
    'usgs'             AS source,
    load_id,
    schema_name,
    status,
    inserted_at::TIMESTAMP AS completed_at
  FROM polaris_aws.raw_usgs._dlt_load_status
),
usgs_earthquakes_loads AS (
  SELECT
    'usgs_earthquakes'             AS source,
    load_id,
    schema_name,
    status,
    inserted_at::TIMESTAMP AS completed_at
  FROM polaris_aws.raw_usgs_earthquakes._dlt_load_status
),
usfws_loads AS (
  SELECT
    'usfws'             AS source,
    load_id,
    schema_name,
    status,
    inserted_at::TIMESTAMP AS completed_at
  FROM polaris_aws.raw_usfws._dlt_load_status
),
all_loads AS (
  SELECT * FROM ebird_loads
  UNION ALL SELECT * FROM gbif_loads
  UNION ALL SELECT * FROM avonet_loads
  UNION ALL SELECT * FROM xeno_canto_loads
  UNION ALL SELECT * FROM noaa_loads
  UNION ALL SELECT * FROM usgs_loads
  UNION ALL SELECT * FROM usgs_earthquakes_loads
  UNION ALL SELECT * FROM usfws_loads
),
ebird_rows AS (
  SELECT load_id, rows_loaded AS rows
  FROM polaris_aws.raw_ebird._dlt_load_status
),
gbif_rows AS (
  SELECT load_id, rows_loaded AS rows
  FROM polaris_aws.raw_gbif._dlt_load_status
),
avonet_rows AS (
  SELECT load_id, rows_loaded AS rows
  FROM polaris_aws.raw_avonet._dlt_load_status
),
xeno_canto_rows AS (
  SELECT load_id, rows_loaded AS rows
  FROM polaris_aws.raw_xeno_canto._dlt_load_status
),
noaa_rows AS (
  SELECT load_id, rows_loaded AS rows
  FROM polaris_aws.raw_noaa._dlt_load_status
),
usgs_rows AS (
  SELECT load_id, rows_loaded AS rows
  FROM polaris_aws.raw_usgs._dlt_load_status
),
usgs_earthquakes_rows AS (
  SELECT load_id, rows_loaded AS rows
  FROM polaris_aws.raw_usgs_earthquakes._dlt_load_status
),
usfws_rows AS (
  SELECT load_id, rows_loaded AS rows
  FROM polaris_aws.raw_usfws._dlt_load_status
),
all_rows AS (
  SELECT 'ebird' AS source, load_id, rows FROM ebird_rows
  UNION ALL SELECT 'gbif' AS source, load_id, rows FROM gbif_rows
  UNION ALL SELECT 'avonet' AS source, load_id, rows FROM avonet_rows
  UNION ALL SELECT 'xeno_canto' AS source, load_id, rows FROM xeno_canto_rows
  UNION ALL SELECT 'noaa' AS source, load_id, rows FROM noaa_rows
  UNION ALL SELECT 'usgs' AS source, load_id, rows FROM usgs_rows
  UNION ALL SELECT 'usgs_earthquakes' AS source, load_id, rows FROM usgs_earthquakes_rows
  UNION ALL SELECT 'usfws' AS source, load_id, rows FROM usfws_rows
),
latest_per_source AS (
  SELECT
    source,
    load_id,
    schema_name,
    status,
    completed_at,
    ROW_NUMBER() OVER (PARTITION BY source ORDER BY completed_at DESC) AS rn
  FROM all_loads
)
SELECT
  l.source,
  l.load_id,
  l.schema_name,
  l.status,
  CASE WHEN l.status = 0 THEN 'success' ELSE 'failed' END AS status_label,
  l.completed_at,
  COALESCE(r.rows, 0) AS rows_loaded,
  (CURRENT_TIMESTAMP - l.completed_at) AS age
FROM latest_per_source l
LEFT JOIN all_rows r
  ON r.source = l.source AND r.load_id = l.load_id
WHERE l.rn = 1
ORDER BY l.source
