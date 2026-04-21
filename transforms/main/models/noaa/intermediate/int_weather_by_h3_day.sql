MODEL (
  name noaa.int_weather_by_h3_day,
  kind FULL,
  description 'Daily NOAA weather assigned to each H3 cell in the bird-observation universe via nearest-station join. Station-to-cell mapping is computed once; daily values join in after. H3 resolution 6 matches ebird.int_observations_by_h3_day.',
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

stations AS (
    SELECT
        station_id,
        latitude,
        longitude
    FROM noaa_staging.stg_noaa_stations
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
),

cell_station_distance AS (
    SELECT
        c.h3_cell,
        s.station_id,
        2 * 3959 * ASIN(SQRT(
            POWER(SIN((RADIANS(c.cell_lat) - RADIANS(s.latitude)) / 2), 2)
            + COS(RADIANS(c.cell_lat)) * COS(RADIANS(s.latitude))
              * POWER(SIN((RADIANS(c.cell_lng) - RADIANS(s.longitude)) / 2), 2)
        )) AS distance_miles
    FROM cell_centers c
    CROSS JOIN stations s
),

nearest_station AS (
    SELECT
        h3_cell,
        station_id AS nearest_station_id,
        distance_miles AS nearest_station_distance_miles
    FROM (
        SELECT
            h3_cell,
            station_id,
            distance_miles,
            ROW_NUMBER() OVER (PARTITION BY h3_cell ORDER BY distance_miles) AS rn
        FROM cell_station_distance
    )
    WHERE rn = 1
)

SELECT
    ns.h3_cell,
    fw.observation_date,
    ns.nearest_station_id,
    ns.nearest_station_distance_miles,
    fw.tmax / 10.0 AS tmax_c,
    fw.tmin / 10.0 AS tmin_c,
    fw.prcp / 10.0 AS prcp_mm,
    fw.snow AS snow_mm,
    fw.awnd / 10.0 AS wind_ms,
    fw.last_loaded_at
FROM nearest_station ns
JOIN noaa.fct_daily_weather fw
    ON fw.station = ns.nearest_station_id
