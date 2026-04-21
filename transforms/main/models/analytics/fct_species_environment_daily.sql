MODEL (
  name analytics.fct_species_environment_daily,
  kind FULL,
  description 'Flagship cross-domain mart: bird observations joined to daily weather and streamflow at species x H3 cell (resolution 6, ~36 km^2) x day grain. Answers questions like "which species show up on cold-snap days after heavy rainfall at this gauge." Grain is unique on (species_code, h3_cell, obs_date).',
  grain (species_code, h3_cell, obs_date),
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH obs AS (
    SELECT
        species_code,
        common_name,
        scientific_name,
        h3_cell,
        observation_date AS obs_date,
        n_observations,
        n_checklists,
        total_birds_counted,
        n_notable_observations,
        last_loaded_at AS ebird_last_loaded_at
    FROM ebird.int_observations_by_h3_day
),

weather AS (
    SELECT
        h3_cell,
        observation_date,
        nearest_station_id,
        nearest_station_distance_miles,
        tmax_c,
        tmin_c,
        prcp_mm,
        snow_mm,
        wind_ms,
        last_loaded_at AS noaa_last_loaded_at
    FROM noaa.int_weather_by_h3_day
),

streamflow AS (
    SELECT
        h3_cell,
        observation_date,
        nearest_gauge_id,
        nearest_gauge_distance_miles,
        mean_discharge_cfs,
        mean_gage_height_ft,
        mean_water_temp_c,
        last_loaded_at AS usgs_last_loaded_at
    FROM usgs.int_streamflow_by_h3_day
),

weather_anomaly AS (
    SELECT
        h3_cell,
        observation_date,
        prcp_mm,
        AVG(prcp_mm) OVER (
            PARTITION BY h3_cell
            ORDER BY observation_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS prcp_mm_7d_mean,
        STDDEV_SAMP(prcp_mm) OVER (
            PARTITION BY h3_cell
            ORDER BY observation_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS prcp_mm_7d_stddev
    FROM weather
),

streamflow_anomaly AS (
    SELECT
        h3_cell,
        observation_date,
        mean_discharge_cfs,
        AVG(mean_discharge_cfs) OVER (
            PARTITION BY h3_cell
            ORDER BY observation_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS discharge_cfs_7d_mean,
        STDDEV_SAMP(mean_discharge_cfs) OVER (
            PARTITION BY h3_cell
            ORDER BY observation_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS discharge_cfs_7d_stddev
    FROM streamflow
)

SELECT
    o.species_code,
    o.common_name,
    o.scientific_name,
    o.h3_cell,
    o.obs_date,

    o.n_observations,
    o.n_checklists,
    o.total_birds_counted,
    o.n_notable_observations,

    w.nearest_station_id,
    ROUND(w.nearest_station_distance_miles::NUMERIC, 2)
        AS nearest_station_distance_miles,
    ROUND(w.tmax_c::NUMERIC, 1) AS tmax_c,
    ROUND(w.tmin_c::NUMERIC, 1) AS tmin_c,
    ROUND((w.tmax_c - w.tmin_c)::NUMERIC, 1) AS temp_range_c,
    ROUND(w.prcp_mm::NUMERIC, 2) AS prcp_mm,
    ROUND(w.snow_mm::NUMERIC, 2) AS snow_mm,
    ROUND(w.wind_ms::NUMERIC, 2) AS wind_ms,
    CASE WHEN w.prcp_mm > 0 THEN TRUE ELSE FALSE END AS is_rainy_day,
    CASE WHEN w.tmax_c >= 30 THEN 1 ELSE 0 END AS is_hot_day,

    s.nearest_gauge_id,
    ROUND(s.nearest_gauge_distance_miles::NUMERIC, 2)
        AS nearest_gauge_distance_miles,
    ROUND(s.mean_discharge_cfs::NUMERIC, 2) AS mean_discharge_cfs,
    ROUND(s.mean_gage_height_ft::NUMERIC, 2) AS mean_gage_height_ft,
    ROUND(s.mean_water_temp_c::NUMERIC, 2) AS mean_water_temp_c,

    ROUND(
        CASE
            WHEN wa.prcp_mm_7d_stddev IS NULL OR wa.prcp_mm_7d_stddev = 0 THEN NULL
            ELSE (wa.prcp_mm - wa.prcp_mm_7d_mean) / wa.prcp_mm_7d_stddev
        END::NUMERIC,
        3
    ) AS prcp_mm_z_7d,
    ROUND(
        CASE
            WHEN sa.discharge_cfs_7d_stddev IS NULL OR sa.discharge_cfs_7d_stddev = 0 THEN NULL
            ELSE (sa.mean_discharge_cfs - sa.discharge_cfs_7d_mean) / sa.discharge_cfs_7d_stddev
        END::NUMERIC,
        3
    ) AS discharge_cfs_z_7d,

    h3_cell_to_lat(o.h3_cell) AS cell_center_lat,
    h3_cell_to_lng(o.h3_cell) AS cell_center_lng,

    o.ebird_last_loaded_at,
    w.noaa_last_loaded_at,
    s.usgs_last_loaded_at,
    CURRENT_TIMESTAMP AS last_updated_at

FROM obs o
LEFT JOIN weather w
    ON w.h3_cell = o.h3_cell
    AND w.observation_date = o.obs_date
LEFT JOIN streamflow s
    ON s.h3_cell = o.h3_cell
    AND s.observation_date = o.obs_date
LEFT JOIN weather_anomaly wa
    ON wa.h3_cell = o.h3_cell
    AND wa.observation_date = o.obs_date
LEFT JOIN streamflow_anomaly sa
    ON sa.h3_cell = o.h3_cell
    AND sa.observation_date = o.obs_date
