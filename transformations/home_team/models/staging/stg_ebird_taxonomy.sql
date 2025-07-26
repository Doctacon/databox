MODEL (
  name sqlmesh_example.stg_ebird_taxonomy,
  kind VIEW,
  description 'Staging model for eBird taxonomy reference data'
);

SELECT
    "speciesCode" AS species_code,
    "comName" AS common_name,
    "sciName" AS scientific_name,
    "taxonOrder" AS taxonomic_order,
    "category" AS taxonomic_category,
    "familyComName" AS family_common_name,
    "familySciName" AS family_scientific_name,
    "_loaded_at"::timestamp AS loaded_at
FROM raw_ebird_data.taxonomy