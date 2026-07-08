MODEL (
  name environmental_observations.dim_species,
  kind FULL,
  description 'CDM species dimension from eBird taxonomy and species list.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH taxonomy_ranked AS (
  SELECT
    species_code,
    com_name AS common_name,
    sci_name AS scientific_name,
    taxon_order::DOUBLE AS taxonomic_order,
    category AS taxonomic_category,
    family_code,
    family_com_name AS family_common_name,
    family_sci_name AS family_scientific_name,
    report_as,
    extinct,
    extinct_year,
    _loaded_at::TIMESTAMP AS loaded_at,
    ROW_NUMBER() OVER (PARTITION BY species_code ORDER BY _loaded_at DESC) AS rn
  FROM raw_ebird.taxonomy
  WHERE species_code IS NOT NULL
),
species_list_ranked AS (
  SELECT
    species_code,
    region,
    "order"::DOUBLE AS taxonomic_order,
    _loaded_at::TIMESTAMP AS loaded_at,
    ROW_NUMBER() OVER (PARTITION BY species_code ORDER BY _loaded_at DESC) AS rn
  FROM raw_ebird.species_list
  WHERE species_code IS NOT NULL
),
merged AS (
  SELECT
    'ebird_api' AS source_pipeline,
    t.species_code AS source_id,
    t.species_code,
    t.common_name,
    t.scientific_name,
    t.taxonomic_order,
    t.taxonomic_category,
    t.family_code,
    t.family_common_name,
    t.family_scientific_name,
    t.report_as,
    t.extinct,
    t.extinct_year,
    s.region,
    COALESCE(t.loaded_at, s.loaded_at) AS loaded_at
  FROM taxonomy_ranked t
  LEFT JOIN species_list_ranked s
    ON s.species_code = t.species_code AND s.rn = 1
  WHERE t.rn = 1

  UNION ALL

  SELECT
    'ebird_api' AS source_pipeline,
    s.species_code AS source_id,
    s.species_code,
    NULL AS common_name,
    NULL AS scientific_name,
    s.taxonomic_order,
    NULL AS taxonomic_category,
    NULL AS family_code,
    NULL AS family_common_name,
    NULL AS family_scientific_name,
    NULL AS report_as,
    NULL AS extinct,
    NULL AS extinct_year,
    s.region,
    s.loaded_at
  FROM species_list_ranked s
  LEFT JOIN taxonomy_ranked t
    ON t.species_code = s.species_code AND t.rn = 1
  WHERE s.rn = 1 AND t.species_code IS NULL
)
SELECT
  md5('environmental_observations|species|' || source_pipeline || '|' || source_id) AS species_sk,
  source_pipeline,
  source_id,
  species_code,
  common_name,
  scientific_name,
  taxonomic_order,
  taxonomic_category,
  family_code,
  family_common_name,
  family_scientific_name,
  report_as,
  extinct,
  extinct_year,
  region,
  loaded_at
FROM merged

UNION ALL

SELECT
  md5('environmental_observations|species|UNKNOWN') AS species_sk,
  'sentinel' AS source_pipeline,
  'UNKNOWN' AS source_id,
  NULL AS species_code,
  'Unknown species' AS common_name,
  NULL AS scientific_name,
  NULL AS taxonomic_order,
  NULL AS taxonomic_category,
  NULL AS family_code,
  NULL AS family_common_name,
  NULL AS family_scientific_name,
  NULL AS report_as,
  NULL AS extinct,
  NULL AS extinct_year,
  NULL AS region,
  NULL AS loaded_at
