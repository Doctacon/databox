MODEL (
  name noaa.fct_daily_weather,
  kind FULL,
  description 'Daily weather facts pivoted from normalized observations to one row per station per date'
);

WITH pivoted AS (
    SELECT
        station,
        observation_date,
        location_id,
        MAX(CASE WHEN datatype = 'TMAX' THEN value END) AS tmax,
        MAX(CASE WHEN datatype = 'TMIN' THEN value END) AS tmin,
        MAX(CASE WHEN datatype = 'PRCP' THEN value END) AS prcp,
        MAX(CASE WHEN datatype = 'SNOW' THEN value END) AS snow,
        MAX(CASE WHEN datatype = 'AWND' THEN value END) AS awnd,
        COUNT(*) AS observation_count,
        COUNT(CASE WHEN value IS NULL THEN 1 END) AS missing_value_count,
        MIN(loaded_at) AS first_loaded_at,
        MAX(loaded_at) AS last_loaded_at
    FROM noaa.stg_noaa_daily_weather
    GROUP BY station, observation_date, location_id
)

SELECT
    station,
    observation_date,
    location_id,
    tmax,
    tmin,
    prcp,
    snow,
    awnd,

    CASE
        WHEN tmax IS NOT NULL AND tmin IS NOT NULL
        THEN ROUND(tmax - tmin, 2)
    END AS temp_range,

    observation_count,
    missing_value_count,
    ROUND(
        CASE
            WHEN observation_count > 0
            THEN (observation_count - missing_value_count)::DOUBLE / observation_count * 100
            ELSE 0
        END, 1
    ) AS pct_data_completeness,

    COUNT(CASE WHEN tmax IS NOT NULL THEN 1 END) OVER (
        PARTITION BY station ORDER BY observation_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS days_with_tmax_7d,

    first_loaded_at,
    last_loaded_at,
    CURRENT_TIMESTAMP AS last_updated_at

FROM pivoted
ORDER BY station, observation_date
