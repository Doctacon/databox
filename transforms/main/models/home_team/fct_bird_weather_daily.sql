MODEL (
  name home_team.fct_bird_weather_daily,
  kind FULL,
  description 'eBird daily observations joined with NOAA weather conditions — one row per region x date x species'
);

-- NOAA GHCND unit conversion: TMAX/TMIN in tenths of °C, PRCP in tenths of mm, AWND in tenths of m/s
WITH az_weather AS (
    SELECT
        observation_date,
        AVG(tmax / 10.0)             AS avg_tmax_c,
        AVG(tmin / 10.0)             AS avg_tmin_c,
        AVG(prcp / 10.0)             AS avg_prcp_mm,
        AVG(snow)                    AS avg_snow_mm,
        AVG(awnd / 10.0)             AS avg_wind_ms,
        COUNT(*)                     AS station_count
    FROM noaa.fct_daily_weather
    WHERE tmax IS NOT NULL OR tmin IS NOT NULL
    GROUP BY observation_date
)

SELECT
    b.region_code,
    b.observation_date,
    b.species_code,
    b.common_name,
    b.scientific_name,
    b.family_common_name,
    b.taxonomic_category,
    b.season,

    b.observation_count,
    b.submission_count,
    b.location_count,
    b.total_birds_counted,
    b.avg_flock_size,
    b.notable_observations,
    b.popularity_score,

    ROUND(w.avg_tmax_c::NUMERIC, 1)                           AS avg_tmax_c,
    ROUND(w.avg_tmin_c::NUMERIC, 1)                           AS avg_tmin_c,
    ROUND((w.avg_tmax_c - w.avg_tmin_c)::NUMERIC, 1)          AS daily_temp_range_c,
    ROUND(w.avg_prcp_mm::NUMERIC, 2)                          AS avg_prcp_mm,
    ROUND(w.avg_snow_mm::NUMERIC, 2)                          AS avg_snow_mm,
    ROUND(w.avg_wind_ms::NUMERIC, 2)                          AS avg_wind_ms,
    CASE WHEN w.avg_prcp_mm > 0 THEN TRUE ELSE FALSE END       AS is_rainy_day,
    w.station_count                                            AS weather_station_count,

    CURRENT_TIMESTAMP AS last_updated_at

FROM ebird.fct_daily_bird_observations b
LEFT JOIN az_weather w ON b.observation_date = w.observation_date
ORDER BY b.region_code, b.observation_date DESC, b.observation_count DESC
