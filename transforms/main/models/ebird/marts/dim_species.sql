MODEL (
  name ebird.dim_species,
  kind FULL,
  description 'Species dimension from eBird taxonomy — one row per species_code',
  grants (select_ = ['staging_reader', 'domain_reader'])
);

SELECT DISTINCT ON (species_code)
    species_code,
    common_name,
    scientific_name,
    taxonomic_order,
    taxonomic_category,
    family_common_name,
    family_scientific_name,
    loaded_at
FROM ebird_staging.stg_ebird_taxonomy
ORDER BY species_code, loaded_at DESC
