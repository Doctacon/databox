MODEL (
  name usgs.int_streamflow_by_h3_day,
  kind FULL,
  description 'Daily USGS streamflow assigned to each H3 cell in the bird-observation universe via nearest-gauge join. Cell-to-gauge mapping is computed once; daily values join in after. H3 resolution 6 matches ebird.int_observations_by_h3_day.',
  grants (select_ = ['staging_reader', 'domain_reader'])
);

WITH cells AS (
    SELECT DISTINCT h3_cell
    FROM ebird.int_observations_by_h3_day
),

cell_centers AS (
    SELECT
        h3_cell,
        h3_cell_to_lat(h3_cell) AS cell_lat,
        h3_cell_to_lng(h3_cell) AS cell_lng
    FROM cells
),

gauges AS (
    SELECT DISTINCT
        site_no,
        latitude,
        longitude
    FROM usgs_staging.stg_usgs_sites
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
),

cell_gauge_distance AS (
    SELECT
        c.h3_cell,
        g.site_no,
        2 * 3959 * ASIN(SQRT(
            POWER(SIN((RADIANS(c.cell_lat) - RADIANS(g.latitude)) / 2), 2)
            + COS(RADIANS(c.cell_lat)) * COS(RADIANS(g.latitude))
              * POWER(SIN((RADIANS(c.cell_lng) - RADIANS(g.longitude)) / 2), 2)
        )) AS distance_miles
    FROM cell_centers c
    CROSS JOIN gauges g
),

nearest_gauge AS (
    SELECT
        h3_cell,
        site_no AS nearest_gauge_id,
        distance_miles AS nearest_gauge_distance_miles
    FROM (
        SELECT
            h3_cell,
            site_no,
            distance_miles,
            ROW_NUMBER() OVER (PARTITION BY h3_cell ORDER BY distance_miles) AS rn
        FROM cell_gauge_distance
    )
    WHERE rn = 1
)

SELECT
    ng.h3_cell,
    fs.observation_date,
    ng.nearest_gauge_id,
    ng.nearest_gauge_distance_miles,
    fs.discharge_cfs AS mean_discharge_cfs,
    fs.gage_height_ft AS mean_gage_height_ft,
    fs.water_temp_c AS mean_water_temp_c,
    fs.last_loaded_at
FROM nearest_gauge ng
JOIN usgs.fct_daily_streamflow fs
    ON fs.site_no = ng.nearest_gauge_id
