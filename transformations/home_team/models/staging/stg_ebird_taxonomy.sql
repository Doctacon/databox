MODEL (
  name sqlmesh_example.stg_ebird_taxonomy,
  kind VIEW,
  description 'Staging model for eBird taxonomy reference data'
);

SELECT
    species_code,
    com_name AS common_name,
    sci_name AS scientific_name,
    taxon_order AS taxonomic_order,
    category AS taxonomic_category,
    family_com_name AS family_common_name,
    family_sci_name AS family_scientific_name,
    _loaded_at::timestamp AS loaded_at
FROM raw_ebird_data.taxonomy
