MODEL (
  name birding_agent.species_lookup,
  kind VIEW,
  description 'Planner-ready bird species lookup from the conformed environmental observations species dimension.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

SELECT
  md5('birding_agent|species_lookup|conformed|' || species_sk) AS species_lookup_id,
  source_pipeline AS evidence_source,
  'environmental_observations.dim_species' AS source_table,
  source_id AS source_record_id,
  species_code,
  common_name,
  scientific_name,
  taxonomic_order,
  taxonomic_category,
  COALESCE(family_common_name, gbif_family) AS family_name,
  genus,
  gbif_taxon_rank AS taxon_rank,
  gbif_taxon_key AS taxon_key,
  gbif_accepted_taxon_key AS accepted_taxon_key,
  region AS region_code,
  loaded_at
FROM environmental_observations.dim_species
WHERE source_pipeline != 'sentinel'
