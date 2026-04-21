MODEL (
  name usgs_earthquakes.fct_daily_earthquakes,
  kind FULL,
  description 'Daily earthquake summary — one row per UTC day, counts and magnitude stats',
  grants (select_ = ['staging_reader', 'domain_reader'])
);

SELECT
    CAST(event_time AS DATE) AS event_date,
    COUNT(*) AS event_count,
    MAX(magnitude) AS max_magnitude,
    ROUND(AVG(magnitude)::NUMERIC, 3) AS avg_magnitude,
    MAX(significance) AS max_significance,
    SUM(CASE WHEN tsunami_flag = 1 THEN 1 ELSE 0 END) AS tsunami_alert_count,
    MAX(loaded_at) AS last_updated_at
FROM usgs_earthquakes_staging.stg_usgs_earthquakes_events
WHERE event_time IS NOT NULL
GROUP BY CAST(event_time AS DATE)
