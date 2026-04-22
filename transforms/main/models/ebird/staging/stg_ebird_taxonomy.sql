-- Generated from soda/contracts/ebird_staging/stg_ebird_taxonomy.yaml by scripts/generate_staging.py.
-- DO NOT EDIT by hand — run `python scripts/generate_staging.py` to regenerate.
MODEL (
  name ebird_staging.stg_ebird_taxonomy,
  kind FULL,
  description 'Staging model for eBird taxonomy reference data',
  grants (select_ = ['staging_reader'])
);

SELECT
    species_code,
    com_name AS common_name,
    sci_name AS scientific_name,
    taxon_order AS taxonomic_order,
    category AS taxonomic_category,
    family_com_name AS family_common_name,
    family_sci_name AS family_scientific_name,
    _loaded_at::TIMESTAMP AS loaded_at
FROM raw_ebird.main.taxonomy
