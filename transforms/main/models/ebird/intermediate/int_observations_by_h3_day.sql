MODEL (
  name ebird.int_observations_by_h3_day,
  kind FULL,
  description 'eBird observations rolled up to H3 cell x species x observation_date. H3 resolution 6 (~36 km^2 hex). Feeds analytics.fct_species_environment_daily.',
  grants (select_ = ['staging_reader', 'domain_reader'])
);

SELECT
    h3_latlng_to_cell_string(latitude, longitude, 6) AS h3_cell,
    observation_date,
    species_code,
    ANY_VALUE(common_name) AS common_name,
    ANY_VALUE(scientific_name) AS scientific_name,
    COUNT(*) AS n_observations,
    COUNT(DISTINCT submission_id) AS n_checklists,
    SUM(count) AS total_birds_counted,
    SUM(CASE WHEN is_notable THEN 1 ELSE 0 END) AS n_notable_observations,
    MAX(loaded_at) AS last_loaded_at
FROM ebird_staging.stg_ebird_observations
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
  AND observation_date IS NOT NULL
GROUP BY h3_cell, observation_date, species_code
