MODEL (
  name sqlmesh_example.fct_daily_bird_observations,
  kind FULL,
  description 'Daily bird observation facts aggregated by region, date, and species'
);

WITH daily_observations AS (
    SELECT
        region_code,
        observation_date,
        species_code,
        common_name,
        scientific_name,
        family_common_name,
        taxonomic_category,
        season,

        -- Observation metrics
        COUNT(DISTINCT submission_id) AS submission_count,
        COUNT(DISTINCT location_id) AS location_count,
        COUNT(*) AS observation_count,

        -- Bird count metrics
        SUM(CASE WHEN count IS NOT NULL THEN count ELSE 0 END) AS total_birds_counted,
        AVG(CASE WHEN count IS NOT NULL THEN count ELSE NULL END) AS avg_flock_size,
        MAX(CASE WHEN count IS NOT NULL THEN count ELSE NULL END) AS max_flock_size,

        -- Count of observations with actual numbers vs. presence only
        COUNT(CASE WHEN count IS NOT NULL THEN 1 END) AS counted_observations,
        COUNT(CASE WHEN count IS NULL THEN 1 END) AS presence_only_observations,

        -- Time-based metrics
        COUNT(CASE WHEN time_of_day = 'Morning' THEN 1 END) AS morning_observations,
        COUNT(CASE WHEN time_of_day = 'Afternoon' THEN 1 END) AS afternoon_observations,
        COUNT(CASE WHEN time_of_day = 'Evening' THEN 1 END) AS evening_observations,
        COUNT(CASE WHEN time_of_day = 'Night' THEN 1 END) AS night_observations,

        -- Special observations
        COUNT(CASE WHEN is_notable THEN 1 END) AS notable_observations,
        COUNT(CASE WHEN is_flock THEN 1 END) AS flock_observations,

        -- Data quality
        COUNT(CASE WHEN is_valid THEN 1 END) AS valid_observations,
        COUNT(CASE WHEN is_reviewed THEN 1 END) AS reviewed_observations,

        -- Geographic spread
        COUNT(DISTINCT ROUND(latitude, 2) || ',' || ROUND(longitude, 2)) AS unique_locations_approx,

        MIN(loaded_at) AS first_loaded_at,
        MAX(loaded_at) AS last_loaded_at

    FROM sqlmesh_example.int_ebird_enriched_observations
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
)

SELECT
    -- Primary keys
    region_code,
    observation_date,
    species_code,

    -- Species information
    common_name,
    scientific_name,
    family_common_name,
    taxonomic_category,
    season,

    -- Observation metrics
    submission_count,
    location_count,
    observation_count,

    -- Bird count metrics
    total_birds_counted,
    ROUND(avg_flock_size, 2) AS avg_flock_size,
    max_flock_size,

    -- Observation type breakdown
    counted_observations,
    presence_only_observations,
    ROUND(
        CASE
            WHEN observation_count > 0
            THEN counted_observations::DOUBLE / observation_count * 100
            ELSE 0
        END, 1
    ) AS pct_counted_observations,

    -- Time distribution
    morning_observations,
    afternoon_observations,
    evening_observations,
    night_observations,

    -- Special categories
    notable_observations,
    flock_observations,

    -- Data quality metrics
    valid_observations,
    reviewed_observations,
    ROUND(
        CASE
            WHEN observation_count > 0
            THEN valid_observations::DOUBLE / observation_count * 100
            ELSE 0
        END, 1
    ) AS pct_valid_observations,

    -- Geographic metrics
    unique_locations_approx,
    ROUND(
        CASE
            WHEN location_count > 0
            THEN observation_count::DOUBLE / location_count
            ELSE 0
        END, 2
    ) AS avg_observations_per_location,

    -- Popularity score (combination of observations and locations)
    ROUND(
        LOG(observation_count + 1) * LOG(location_count + 1), 2
    ) AS popularity_score,

    -- Metadata
    first_loaded_at,
    last_loaded_at,
    CURRENT_TIMESTAMP AS last_updated_at

FROM daily_observations
ORDER BY region_code, observation_date DESC, observation_count DESC
