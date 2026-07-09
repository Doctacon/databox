MODEL (
  name environmental_observations.fact_bird_occurrence,
  kind FULL,
  description 'CDM fact: one row per GBIF bird occurrence key.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH source_rows AS (
  SELECT
    *,
    COALESCE(
      NULLIF(TRIM(accepted_scientific_name), ''),
      NULLIF(TRIM(scientific_name), ''),
      NULLIF(TRIM(species), '')
    ) AS gbif_scientific_name
  FROM raw_gbif.occurrences
  WHERE key IS NOT NULL
),
ranked AS (
  SELECT
    *,
    NULLIF(
      LOWER(TRIM(regexp_replace(TRIM(gbif_scientific_name), '\s*\([^)]*\)\s*$', ''))),
      ''
    ) AS species_natural_key,
    CASE
      WHEN NULLIF(LOWER(TRIM(regexp_replace(TRIM(gbif_scientific_name), '\s*\([^)]*\)\s*$', ''))), '') IS NULL THEN CAST(key AS VARCHAR)
      ELSE CAST(COALESCE(accepted_taxon_key, taxon_key, key) AS VARCHAR)
    END AS gbif_source_id,
    ROW_NUMBER() OVER (PARTITION BY key ORDER BY _loaded_at DESC) AS rn
  FROM source_rows
)
SELECT
  md5('environmental_observations|bird_occurrence|gbif_api|' || CAST(r.key AS VARCHAR)) AS bird_occurrence_sk,
  COALESCE(s.species_sk, md5('environmental_observations|species|UNKNOWN')) AS species_sk,
  'gbif_api' AS source_pipeline,
  CAST(r.key AS VARCHAR) AS source_id,
  r.key AS gbif_key,
  r.gbif_id,
  r.occurrence_id,
  r.dataset_key,
  r.publishing_org_key,
  r.installation_key,
  r.hosting_organization_key,
  r.protocol,
  r.publishing_country,
  r.scientific_name,
  r.accepted_scientific_name,
  r.vernacular_name AS common_name,
  r.kingdom,
  r.phylum,
  r.class_name,
  r.order_name,
  r.family,
  r.genus,
  r.species,
  r.generic_name,
  r.specific_epithet,
  r.taxon_rank,
  r.taxon_key,
  r.accepted_taxon_key,
  r.kingdom_key,
  r.phylum_key,
  r.class_key,
  r.order_key,
  r.family_key,
  r.genus_key,
  r.species_key,
  r.decimal_latitude::DOUBLE AS latitude,
  r.decimal_longitude::DOUBLE AS longitude,
  r.coordinate_uncertainty_in_meters::DOUBLE AS coordinate_uncertainty_in_meters,
  r.country,
  r.country_code,
  r.state_province,
  r.locality,
  r.event_date AS event_date_text,
  TRY_CAST(r.event_date AS DATE) AS event_date,
  r.year::BIGINT AS year,
  r.month::BIGINT AS month,
  r.day::BIGINT AS day,
  r.basis_of_record,
  r.occurrence_status,
  r.establishment_means,
  r.record_number,
  r.recorded_by,
  r.identified_by,
  r.institution_code,
  r.collection_code,
  r.catalog_number,
  r.license,
  r.references AS source_reference_url,
  r.last_interpreted,
  r.last_crawled,
  r.last_parsed,
  r._source_url AS source_url,
  r._query_country_code AS query_country_code,
  r._query_state_province AS query_state_province,
  r._query_taxon_key AS query_taxon_key,
  r._loaded_at::TIMESTAMP AS loaded_at,
  r._dlt_load_id AS dlt_load_id,
  r._dlt_id AS dlt_id
FROM ranked r
LEFT JOIN environmental_observations.dim_species s
  ON s.species_natural_key = r.species_natural_key
  OR (r.species_natural_key IS NULL AND s.source_pipeline = 'gbif_api' AND s.source_id = r.gbif_source_id)
WHERE r.rn = 1
