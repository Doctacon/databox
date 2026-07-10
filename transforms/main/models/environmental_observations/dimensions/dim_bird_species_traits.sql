MODEL (
  name environmental_observations.dim_bird_species_traits,
  kind FULL,
  description 'Exact scientific-name-conformed AVONET v7 species-average bird traits with measurement and dataset provenance.',
  grants (
    select_ = ['staging_reader', 'domain_reader', 'analyst']
  )
);

WITH avonet_normalized AS (
  SELECT
    NULLIF(
      LOWER(TRIM(REGEXP_REPLACE(TRIM(source_scientific_name), '\s*\([^)]*\)\s*$', ''))),
      ''
    ) AS species_natural_key,
    source_scientific_name,
    family,
    order_name,
    avibase_id,
    total_individuals,
    female_individuals,
    male_individuals,
    unknown_sex_individuals,
    complete_measures,
    beak_length_culmen_mm,
    beak_length_nares_mm,
    beak_width_mm,
    beak_depth_mm,
    tarsus_length_mm,
    wing_length_mm,
    kipps_distance_mm,
    secondary_length_mm,
    hand_wing_index,
    tail_length_mm,
    mass_g,
    mass_source,
    mass_reference_other,
    inference,
    traits_inferred,
    reference_species,
    habitat,
    habitat_density_code,
    migration_code,
    trophic_level,
    trophic_niche,
    primary_lifestyle,
    dataset_doi,
    dataset_version,
    dataset_license,
    source_file_id,
    source_file_md5,
    source_url,
    loaded_at,
    _dlt_load_id,
    _dlt_id
  FROM raw_avonet.species_traits
), duplicate_avonet_keys AS (
  SELECT
    species_natural_key
  FROM avonet_normalized
  WHERE
    NOT species_natural_key IS NULL
  GROUP BY
    species_natural_key
  HAVING
    COUNT(*) > 1
), source_guard AS (
  SELECT
    CASE
      WHEN COUNT(*) = 0
      THEN 1
      ELSE ERROR('AVONET normalized scientific names must be unique')
    END AS is_valid
  FROM duplicate_avonet_keys
), matched AS (
  SELECT
    s.species_sk,
    s.species_natural_key,
    a.source_scientific_name,
    a.family,
    a.order_name,
    a.avibase_id,
    a.total_individuals,
    a.female_individuals,
    a.male_individuals,
    a.unknown_sex_individuals,
    a.complete_measures,
    a.beak_length_culmen_mm,
    a.beak_length_nares_mm,
    a.beak_width_mm,
    a.beak_depth_mm,
    a.tarsus_length_mm,
    a.wing_length_mm,
    a.kipps_distance_mm,
    a.secondary_length_mm,
    a.hand_wing_index,
    a.tail_length_mm,
    a.mass_g,
    a.mass_source,
    a.mass_reference_other,
    a.inference,
    a.traits_inferred,
    a.reference_species,
    a.habitat,
    a.habitat_density_code,
    CASE a.habitat_density_code
      WHEN 1
      THEN 'Dense'
      WHEN 2
      THEN 'Semi-open'
      WHEN 3
      THEN 'Open'
    END AS habitat_density_label,
    a.migration_code,
    CASE a.migration_code
      WHEN 1
      THEN 'Sedentary'
      WHEN 2
      THEN 'Partial migrant'
      WHEN 3
      THEN 'Migratory'
    END AS migration_label,
    a.trophic_level,
    a.trophic_niche,
    a.primary_lifestyle,
    a.dataset_doi,
    a.dataset_version,
    a.dataset_license,
    a.source_file_id,
    a.source_file_md5,
    a.source_url,
    a.loaded_at::TIMESTAMP AS loaded_at,
    a._dlt_load_id AS dlt_load_id,
    a._dlt_id AS dlt_id
  FROM avonet_normalized AS a
  INNER JOIN environmental_observations.dim_species AS s
    ON s.species_natural_key = a.species_natural_key
  WHERE
    NOT a.species_natural_key IS NULL
    AND NOT s.species_natural_key IS NULL
    AND s.source_pipeline <> 'sentinel'
), duplicate_matches AS (
  SELECT
    species_natural_key
  FROM matched
  GROUP BY
    species_natural_key
  HAVING
    COUNT(*) > 1
), match_guard AS (
  SELECT
    CASE
      WHEN COUNT(*) = 0
      THEN 1
      ELSE ERROR('AVONET trait model must contain one row per conformed species')
    END AS is_valid
  FROM duplicate_matches
)
SELECT
  MD5('environmental_observations|bird_species_traits|' || m.species_natural_key) AS bird_species_traits_sk,
  m.species_sk,
  m.species_natural_key,
  m.source_scientific_name,
  m.family,
  m.order_name,
  m.avibase_id,
  m.total_individuals,
  m.female_individuals,
  m.male_individuals,
  m.unknown_sex_individuals,
  m.complete_measures,
  m.beak_length_culmen_mm,
  m.beak_length_nares_mm,
  m.beak_width_mm,
  m.beak_depth_mm,
  m.tarsus_length_mm,
  m.wing_length_mm,
  m.kipps_distance_mm,
  m.secondary_length_mm,
  m.hand_wing_index,
  m.tail_length_mm,
  m.mass_g,
  m.mass_source,
  m.mass_reference_other,
  m.inference,
  m.traits_inferred,
  m.reference_species,
  m.habitat,
  m.habitat_density_code,
  m.habitat_density_label,
  m.migration_code,
  m.migration_label,
  m.trophic_level,
  m.trophic_niche,
  m.primary_lifestyle,
  m.dataset_doi,
  m.dataset_version,
  m.dataset_license,
  m.source_file_id,
  m.source_file_md5,
  m.source_url,
  m.loaded_at,
  m.dlt_load_id,
  m.dlt_id
FROM source_guard AS source_check
CROSS JOIN match_guard AS match_check
LEFT JOIN matched AS m
  ON TRUE
WHERE
  source_check.is_valid = 1
  AND match_check.is_valid = 1
  AND NOT m.species_sk IS NULL
