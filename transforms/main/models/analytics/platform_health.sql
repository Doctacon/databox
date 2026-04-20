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
  FROM raw_ebird.main._dlt_loads
),
noaa_loads AS (
  SELECT
    'noaa'              AS source,
    load_id,
    schema_name,
    status,
    inserted_at::TIMESTAMP AS completed_at
  FROM raw_noaa.main._dlt_loads
),
usgs_loads AS (
  SELECT
    'usgs'              AS source,
    load_id,
    schema_name,
    status,
    inserted_at::TIMESTAMP AS completed_at
  FROM raw_usgs.main._dlt_loads
),
all_loads AS (
  SELECT * FROM ebird_loads
  UNION ALL SELECT * FROM noaa_loads
  UNION ALL SELECT * FROM usgs_loads
),
ebird_rows AS (
  SELECT _dlt_load_id AS load_id, SUM(n)::BIGINT AS rows FROM (
    SELECT _dlt_load_id, COUNT(*) AS n FROM raw_ebird.main.recent_observations GROUP BY 1
    UNION ALL SELECT _dlt_load_id, COUNT(*) FROM raw_ebird.main.notable_observations GROUP BY 1
    UNION ALL SELECT _dlt_load_id, COUNT(*) FROM raw_ebird.main.hotspots GROUP BY 1
    UNION ALL SELECT _dlt_load_id, COUNT(*) FROM raw_ebird.main.species_list GROUP BY 1
  ) t GROUP BY 1
),
noaa_rows AS (
  SELECT _dlt_load_id AS load_id, SUM(n)::BIGINT AS rows FROM (
    SELECT _dlt_load_id, COUNT(*) AS n FROM raw_noaa.main.daily_weather GROUP BY 1
    UNION ALL SELECT _dlt_load_id, COUNT(*) FROM raw_noaa.main.stations GROUP BY 1
  ) t GROUP BY 1
),
usgs_rows AS (
  SELECT _dlt_load_id AS load_id, SUM(n)::BIGINT AS rows FROM (
    SELECT _dlt_load_id, COUNT(*) AS n FROM raw_usgs.main.daily_values GROUP BY 1
    UNION ALL SELECT _dlt_load_id, COUNT(*) FROM raw_usgs.main.sites GROUP BY 1
  ) t GROUP BY 1
),
all_rows AS (
  SELECT 'ebird' AS source, load_id, rows FROM ebird_rows
  UNION ALL SELECT 'noaa', load_id, rows FROM noaa_rows
  UNION ALL SELECT 'usgs', load_id, rows FROM usgs_rows
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
