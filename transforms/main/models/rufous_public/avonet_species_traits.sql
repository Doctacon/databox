MODEL (
  name rufous_public.avonet_species_traits,
  kind FULL,
  description 'Commercially reusable AVONET v7 morphology and ecology projection for exact scientific-name matching; geographical range fields are not included.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH normalized AS (
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
    CASE habitat_density_code
      WHEN 1 THEN 'Dense'
      WHEN 2 THEN 'Semi-open'
      WHEN 3 THEN 'Open'
    END AS habitat_density_label,
    migration_code,
    CASE migration_code
      WHEN 1 THEN 'Sedentary'
      WHEN 2 THEN 'Partial migrant'
      WHEN 3 THEN 'Migratory'
    END AS migration_label,
    trophic_level,
    trophic_niche,
    primary_lifestyle,
    dataset_doi,
    dataset_version,
    dataset_license,
    source_file_id,
    source_file_md5,
    source_url,
    loaded_at::TIMESTAMP AS loaded_at
  FROM raw_avonet.species_traits
), contract_violations AS (
  SELECT species_natural_key
  FROM normalized
  WHERE species_natural_key IS NULL
    OR NULLIF(TRIM(source_scientific_name), '') IS NULL
    OR NULLIF(TRIM(family), '') IS NULL
    OR NULLIF(TRIM(order_name), '') IS NULL
    OR NULLIF(TRIM(avibase_id), '') IS NULL
    OR total_individuals IS NULL
    OR total_individuals < 0
    OR female_individuals IS NULL
    OR female_individuals < 0
    OR male_individuals IS NULL
    OR male_individuals < 0
    OR unknown_sex_individuals IS NULL
    OR unknown_sex_individuals < 0
    OR complete_measures IS NULL
    OR complete_measures < 0
    OR inference IS NULL
    OR habitat_density_code IS NULL
    OR habitat_density_code NOT BETWEEN 1 AND 3
    OR (migration_code IS NOT NULL AND migration_code NOT BETWEEN 1 AND 3)
    OR NULLIF(TRIM(primary_lifestyle), '') IS NULL
    OR dataset_doi IS DISTINCT FROM '10.6084/m9.figshare.16586228.v7'
    OR dataset_version IS DISTINCT FROM 'v7'
    OR dataset_license IS DISTINCT FROM 'CC BY 4.0'
    OR source_file_id IS DISTINCT FROM 34480856
    OR source_file_md5 IS DISTINCT FROM '1445afdcfb6df784010c2ca034544bc8'
    OR source_url IS DISTINCT FROM 'https://ndownloader.figshare.com/files/34480856'
    OR loaded_at IS NULL
), duplicate_names AS (
  SELECT species_natural_key
  FROM normalized
  GROUP BY species_natural_key
  HAVING COUNT(*) > 1
), source_guard AS (
  SELECT CASE
    WHEN (SELECT COUNT(*) FROM contract_violations) = 0
      AND (SELECT COUNT(*) FROM duplicate_names) = 0
      AND (SELECT COUNT(*) FROM normalized) > 0
    THEN 1
    ELSE ERROR('AVONET public trait source contract is invalid')
  END AS is_valid
)
SELECT
  n.species_natural_key,
  n.source_scientific_name,
  n.family,
  n.order_name,
  n.avibase_id,
  n.total_individuals,
  n.female_individuals,
  n.male_individuals,
  n.unknown_sex_individuals,
  n.complete_measures,
  n.beak_length_culmen_mm,
  n.beak_length_nares_mm,
  n.beak_width_mm,
  n.beak_depth_mm,
  n.tarsus_length_mm,
  n.wing_length_mm,
  n.kipps_distance_mm,
  n.secondary_length_mm,
  n.hand_wing_index,
  n.tail_length_mm,
  n.mass_g,
  n.mass_source,
  n.mass_reference_other,
  n.inference,
  n.traits_inferred,
  n.reference_species,
  n.habitat,
  n.habitat_density_code,
  n.habitat_density_label,
  n.migration_code,
  n.migration_label,
  n.trophic_level,
  n.trophic_niche,
  n.primary_lifestyle,
  n.dataset_doi,
  n.dataset_version,
  n.dataset_license,
  n.source_file_id,
  n.source_file_md5,
  n.source_url,
  n.loaded_at
FROM normalized AS n
CROSS JOIN source_guard AS guard
WHERE guard.is_valid = 1
;
