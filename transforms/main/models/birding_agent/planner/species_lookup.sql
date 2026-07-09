MODEL (
  name birding_agent.species_lookup,
  kind VIEW,
  description 'Planner-ready bird species lookup from eBird CDM species plus GBIF occurrence taxonomy fields.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH ebird_species AS (
  SELECT
    md5('birding_agent|species_lookup|ebird|' || source_id) AS species_lookup_id,
    'ebird' AS evidence_source,
    'environmental_observations.dim_species' AS source_table,
    source_id AS source_record_id,
    species_code,
    common_name,
    scientific_name,
    taxonomic_order,
    taxonomic_category,
    family_common_name AS family_name,
    NULL AS genus,
    NULL AS taxon_rank,
    NULL::BIGINT AS taxon_key,
    NULL::BIGINT AS accepted_taxon_key,
    region AS region_code,
    loaded_at
  FROM environmental_observations.dim_species
  WHERE source_pipeline = 'ebird_api'
    AND source_id IS NOT NULL
),
gbif_taxa AS (
  SELECT
    COALESCE(
      CAST(accepted_taxon_key AS VARCHAR),
      CAST(taxon_key AS VARCHAR),
      NULLIF(accepted_scientific_name, ''),
      NULLIF(scientific_name, ''),
      CAST(key AS VARCHAR)
    ) AS source_record_id,
    vernacular_name AS common_name,
    COALESCE(accepted_scientific_name, scientific_name, species) AS scientific_name,
    family AS family_name,
    genus,
    taxon_rank,
    taxon_key,
    accepted_taxon_key,
    _query_state_province AS region_code,
    _loaded_at::TIMESTAMP AS loaded_at,
    ROW_NUMBER() OVER (
      PARTITION BY COALESCE(
        CAST(accepted_taxon_key AS VARCHAR),
        CAST(taxon_key AS VARCHAR),
        NULLIF(accepted_scientific_name, ''),
        NULLIF(scientific_name, ''),
        CAST(key AS VARCHAR)
      )
      ORDER BY _loaded_at DESC, key DESC
    ) AS rn
  FROM raw_gbif.occurrences
  WHERE key IS NOT NULL
)
SELECT
  species_lookup_id,
  evidence_source,
  source_table,
  source_record_id,
  species_code,
  common_name,
  scientific_name,
  taxonomic_order,
  taxonomic_category,
  family_name,
  genus,
  taxon_rank,
  taxon_key,
  accepted_taxon_key,
  region_code,
  loaded_at
FROM ebird_species

UNION ALL

SELECT
  md5('birding_agent|species_lookup|gbif|' || source_record_id) AS species_lookup_id,
  'gbif' AS evidence_source,
  'raw_gbif.occurrences' AS source_table,
  source_record_id,
  NULL AS species_code,
  common_name,
  scientific_name,
  NULL::DOUBLE AS taxonomic_order,
  NULL AS taxonomic_category,
  family_name,
  genus,
  taxon_rank,
  taxon_key,
  accepted_taxon_key,
  region_code,
  loaded_at
FROM gbif_taxa
WHERE rn = 1 AND source_record_id IS NOT NULL
