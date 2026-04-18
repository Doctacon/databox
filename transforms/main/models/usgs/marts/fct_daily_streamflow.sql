MODEL (
  name usgs.fct_daily_streamflow,
  kind FULL,
  description 'Daily streamflow facts pivoted to one row per site per date with key hydrological metrics',
  grants (select_ = ['staging_reader', 'domain_reader'])
);

WITH pivoted AS (
    SELECT
        site_no,
        observation_date,
        state_cd,
        MAX(CASE WHEN parameter_cd = '00060' THEN value END) AS discharge_cfs,
        MAX(CASE WHEN parameter_cd = '00065' THEN value END) AS gage_height_ft,
        MAX(CASE WHEN parameter_cd = '00010' THEN value END) AS water_temp_c,
        COUNT(*) AS parameter_count,
        MIN(loaded_at) AS first_loaded_at,
        MAX(loaded_at) AS last_loaded_at
    FROM usgs_staging.stg_usgs_daily_values
    GROUP BY site_no, observation_date, state_cd
),

with_site AS (
    SELECT
        p.*,
        s.site_name,
        s.latitude,
        s.longitude,
        s.huc_cd,
        s.drainage_area_sqmi
    FROM pivoted p
    LEFT JOIN usgs_staging.stg_usgs_sites s USING (site_no)
)

SELECT
    site_no,
    site_name,
    observation_date,
    state_cd,
    latitude,
    longitude,
    huc_cd,
    drainage_area_sqmi,

    discharge_cfs,
    gage_height_ft,
    water_temp_c,

    CASE
        WHEN water_temp_c IS NOT NULL
        THEN ROUND((water_temp_c * 9.0 / 5.0 + 32.0)::NUMERIC, 2)
    END AS water_temp_f,

    AVG(discharge_cfs) OVER (
        PARTITION BY site_no ORDER BY observation_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS discharge_7d_avg_cfs,

    parameter_count,
    first_loaded_at,
    last_loaded_at,
    CURRENT_TIMESTAMP AS last_updated_at

FROM with_site
ORDER BY site_no, observation_date
