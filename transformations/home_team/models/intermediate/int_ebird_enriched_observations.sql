MODEL (
  name sqlmesh_example.int_ebird_enriched_observations,
  kind VIEW,
  description 'Intermediate model with enriched bird observations including taxonomy and location details'
);

WITH observations AS (
    SELECT *
    FROM sqlmesh_example.stg_ebird_observations
),

taxonomy AS (
    SELECT *
    FROM sqlmesh_example.stg_ebird_taxonomy
),

hotspots AS (
    SELECT *
    FROM sqlmesh_example.stg_ebird_hotspots
)

SELECT
    o.submission_id,
    o.species_code,
    o.common_name,
    o.scientific_name,
    o.location_id,
    o.location_name,
    o.observation_datetime,
    o.observation_date,
    o.observation_year,
    o.observation_month,
    o.observation_day,
    o.observation_hour,
    o.count,
    o.count_display,
    o.latitude,
    o.longitude,
    o.is_valid,
    o.is_reviewed,
    o.is_location_private,
    o.region_code,
    o.is_notable,

    -- Taxonomy enrichment
    t.taxonomic_order,
    t.taxonomic_category,
    t.family_common_name,
    t.family_scientific_name,

    -- Location enrichment (from hotspot data if available)
    h.country_code,
    h.state_code,
    h.county_code,
    h.total_species_count AS hotspot_total_species,
    h.latest_observation_datetime AS hotspot_latest_observation,

    -- Derived fields
    CASE
        WHEN o.observation_hour BETWEEN 5 AND 11 THEN 'Morning'
        WHEN o.observation_hour BETWEEN 12 AND 17 THEN 'Afternoon'
        WHEN o.observation_hour BETWEEN 18 AND 20 THEN 'Evening'
        ELSE 'Night'
    END AS time_of_day,

    CASE
        WHEN o.observation_month IN (12, 1, 2) THEN 'Winter'
        WHEN o.observation_month IN (3, 4, 5) THEN 'Spring'
        WHEN o.observation_month IN (6, 7, 8) THEN 'Summer'
        ELSE 'Fall'
    END AS season,

    CASE
        WHEN o.count IS NULL THEN False
        WHEN o.count = 1 THEN False
        ELSE True
    END AS is_flock,

    -- Distance from hotspot center (if at hotspot)
    CASE
        WHEN h.latitude IS NOT NULL AND h.longitude IS NOT NULL THEN
            2 * 3959 * ASIN(SQRT(
                POWER(SIN((RADIANS(o.latitude) - RADIANS(h.latitude)) / 2), 2) +
                COS(RADIANS(h.latitude)) * COS(RADIANS(o.latitude)) *
                POWER(SIN((RADIANS(o.longitude) - RADIANS(h.longitude)) / 2), 2)
            ))
        ELSE NULL
    END AS distance_from_hotspot_miles,

    o.loaded_at

FROM observations o
LEFT JOIN taxonomy t ON o.species_code = t.species_code
LEFT JOIN hotspots h ON o.location_id = h.location_id
