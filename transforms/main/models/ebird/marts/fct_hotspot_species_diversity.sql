MODEL (
  name ebird.fct_hotspot_species_diversity,
  kind FULL,
  description 'Per-hotspot biodiversity metrics including Shannon diversity index and species richness'
);

WITH obs AS (
    SELECT *
    FROM ebird.int_ebird_enriched_observations
    WHERE location_id IS NOT NULL
),

species_counts AS (
    SELECT
        location_id,
        species_code,
        common_name AS species_common_name,
        COUNT(*) AS n
    FROM obs
    GROUP BY location_id, species_code, common_name
),

totals AS (
    SELECT location_id, SUM(n) AS total
    FROM species_counts
    GROUP BY location_id
),

shannon AS (
    SELECT
        sc.location_id,
        ROUND(
            -SUM(
                (sc.n::DOUBLE PRECISION / t.total) *
                LN(sc.n::DOUBLE PRECISION / t.total)
            )::NUMERIC, 4
        ) AS shannon_diversity_index
    FROM species_counts sc
    JOIN totals t USING (location_id)
    GROUP BY sc.location_id
),

most_common AS (
    SELECT DISTINCT ON (location_id)
        location_id,
        species_code AS most_common_species_code,
        species_common_name AS most_common_species_name
    FROM species_counts
    ORDER BY location_id, n DESC
),

peak_season AS (
    SELECT DISTINCT ON (location_id)
        location_id,
        season AS peak_season
    FROM (
        SELECT location_id, season, COUNT(*) AS n
        FROM obs
        WHERE season IS NOT NULL
        GROUP BY location_id, season
    ) s
    ORDER BY location_id, n DESC
),

location_stats AS (
    SELECT
        location_id,
        MAX(location_name)        AS location_name,
        MAX(state_code)           AS state_code,
        MAX(county_code)          AS county_code,
        MAX(latitude)             AS latitude,
        MAX(longitude)            AS longitude,
        COUNT(DISTINCT species_code)                         AS total_species_count,
        COUNT(*)                                             AS total_observations,
        COUNT(CASE WHEN is_notable THEN 1 END)               AS notable_observations,
        MIN(observation_date)                                AS first_observation_date,
        MAX(observation_date)                                AS last_observation_date,
        MAX(loaded_at)                                       AS last_loaded_at
    FROM obs
    GROUP BY location_id
)

SELECT
    ls.location_id,
    ls.location_name,
    ls.state_code,
    ls.county_code,
    ls.latitude,
    ls.longitude,
    ls.total_species_count,
    ls.total_observations,
    sh.shannon_diversity_index,
    mc.most_common_species_code,
    mc.most_common_species_name,
    ps.peak_season,
    ROUND(
        (ls.notable_observations::DOUBLE PRECISION / NULLIF(ls.total_observations, 0) * 100)::NUMERIC,
        1
    ) AS pct_notable_observations,
    ls.first_observation_date,
    ls.last_observation_date,
    ls.last_loaded_at,
    CURRENT_TIMESTAMP AS last_updated_at
FROM location_stats ls
LEFT JOIN shannon sh USING (location_id)
LEFT JOIN most_common mc USING (location_id)
LEFT JOIN peak_season ps USING (location_id)
ORDER BY sh.shannon_diversity_index DESC NULLS LAST
