MODEL (
  name environmental_observations.fact_earthquake_event,
  kind FULL,
  description 'CDM fact: one row per USGS earthquake event id.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY id ORDER BY event_updated_at DESC, _loaded_at DESC) AS rn
  FROM raw_usgs_earthquakes.events
  WHERE id IS NOT NULL
)
SELECT
  md5('environmental_observations|earthquake_event|usgs_earthquakes_api|' || id) AS earthquake_event_sk,
  'usgs_earthquakes_api' AS source_pipeline,
  id AS source_id,
  id AS event_id,
  magnitude::DOUBLE AS magnitude,
  magnitude_type,
  place,
  title,
  event_time::TIMESTAMP AS event_time,
  event_updated_at::TIMESTAMP AS event_updated_at,
  longitude::DOUBLE AS longitude,
  latitude::DOUBLE AS latitude,
  depth_km::DOUBLE AS depth_km,
  status,
  tsunami_flag::BIGINT AS tsunami_flag,
  significance::BIGINT AS significance,
  event_type,
  alert,
  url,
  _loaded_at::TIMESTAMP AS loaded_at,
  _dlt_load_id AS dlt_load_id,
  _dlt_id AS dlt_id
FROM ranked
WHERE rn = 1
