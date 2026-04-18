MODEL (
  name home_team.fct_species_weather_preferences,
  kind FULL,
  description 'Per-species weather preference aggregates — what conditions correlate with each species appearing'
);

WITH ranked_seasons AS (
    SELECT DISTINCT ON (species_code)
        species_code,
        season AS dominant_season
    FROM (
        SELECT species_code, season, COUNT(*) AS n
        FROM home_team.fct_bird_weather_daily
        WHERE season IS NOT NULL
        GROUP BY species_code, season
    ) s
    ORDER BY species_code, n DESC
)

SELECT
    b.species_code,
    MAX(b.common_name)       AS common_name,
    MAX(b.scientific_name)   AS scientific_name,
    MAX(b.family_common_name) AS family_common_name,
    MAX(b.taxonomic_category) AS taxonomic_category,

    COUNT(*)                  AS total_observation_days,
    SUM(b.observation_count)  AS total_observations,

    ROUND(AVG(b.avg_tmax_c)::NUMERIC, 1)   AS avg_high_temp_c,
    ROUND(AVG(b.avg_tmin_c)::NUMERIC, 1)   AS avg_low_temp_c,
    ROUND(MIN(b.avg_tmax_c)::NUMERIC, 1)   AS coldest_day_high_c,
    ROUND(MAX(b.avg_tmax_c)::NUMERIC, 1)   AS hottest_day_high_c,
    ROUND(
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY b.avg_tmax_c)::NUMERIC, 1
    ) AS p25_high_temp_c,
    ROUND(
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY b.avg_tmax_c)::NUMERIC, 1
    ) AS p75_high_temp_c,

    ROUND(AVG(b.avg_prcp_mm)::NUMERIC, 2)  AS avg_precip_mm,
    ROUND(
        (COUNT(CASE WHEN b.is_rainy_day THEN 1 END)::DOUBLE PRECISION / NULLIF(COUNT(*), 0) * 100)::NUMERIC,
        1
    ) AS pct_rainy_days,
    ROUND(AVG(b.avg_wind_ms)::NUMERIC, 2)  AS avg_wind_ms,

    rs.dominant_season,

    CURRENT_TIMESTAMP AS last_updated_at

FROM home_team.fct_bird_weather_daily b
LEFT JOIN ranked_seasons rs USING (species_code)
GROUP BY b.species_code, rs.dominant_season
ORDER BY total_observations DESC
