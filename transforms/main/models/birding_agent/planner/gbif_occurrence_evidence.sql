MODEL (
  name birding_agent.gbif_occurrence_evidence,
  kind VIEW,
  description 'Planner-ready GBIF bird occurrence evidence conformed to eBird-first species names with location, license, and source provenance.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH gbif_rows AS (
  SELECT
    *,
    scientific_name AS source_scientific_name,
    NULLIF(
      LOWER(
        TRIM(
          regexp_extract(
            COALESCE(
              NULLIF(TRIM(accepted_scientific_name), ''),
              NULLIF(TRIM(species), ''),
              NULLIF(TRIM(scientific_name), '')
            ),
            '^([A-Za-z][A-Za-z.-]+\s+[A-Za-z][A-Za-z.-]+)',
            1
          )
        )
      ),
      ''
    ) AS species_natural_key
  FROM raw_gbif.occurrences
  WHERE key IS NOT NULL
),
conformed_species AS (
  SELECT * EXCLUDE (rn)
  FROM (
    SELECT
      species_natural_key,
      species_code,
      common_name,
      scientific_name,
      ROW_NUMBER() OVER (
        PARTITION BY species_natural_key
        ORDER BY
          CASE WHEN source_pipeline = 'ebird_api' THEN 0 ELSE 1 END,
          loaded_at DESC NULLS LAST,
          species_sk
      ) AS rn
    FROM environmental_observations.dim_species
    WHERE species_natural_key IS NOT NULL AND source_pipeline != 'sentinel'
  )
  WHERE rn = 1
)
SELECT
  md5('birding_agent|gbif_occurrence|' || CAST(g.key AS VARCHAR)) AS occurrence_evidence_id,
  'gbif' AS evidence_source,
  'raw_gbif.occurrences' AS source_table,
  CAST(g.key AS VARCHAR) AS source_record_id,
  g.key AS gbif_key,
  g.gbif_id,
  g.occurrence_id,
  g.dataset_key,
  g.publishing_org_key,
  g.species_natural_key,
  s.species_code,
  COALESCE(
    NULLIF(TRIM(s.scientific_name), ''),
    NULLIF(TRIM(g.species), ''),
    NULLIF(TRIM(g.accepted_scientific_name), ''),
    NULLIF(TRIM(g.source_scientific_name), '')
  ) AS scientific_name,
  g.source_scientific_name,
  g.accepted_scientific_name,
  COALESCE(NULLIF(TRIM(s.common_name), ''), NULLIF(TRIM(g.vernacular_name), '')) AS common_name,
  g.family,
  g.genus,
  g.species,
  g.taxon_rank,
  g.taxon_key,
  g.accepted_taxon_key,
  g.decimal_latitude AS latitude,
  g.decimal_longitude AS longitude,
  g.coordinate_uncertainty_in_meters,
  g.country,
  g.country_code,
  g.state_province,
  g.locality,
  g.event_date AS event_date_text,
  g.year,
  g.month,
  g.day,
  g.basis_of_record,
  g.occurrence_status,
  g.establishment_means,
  g.license,
  g.references AS source_reference_url,
  g.last_interpreted,
  g.last_crawled,
  g.last_parsed,
  g._source_url,
  g._query_country_code,
  g._query_state_province,
  g._query_taxon_key,
  g._loaded_at::TIMESTAMP AS loaded_at,
  g._dlt_load_id AS dlt_load_id,
  g._dlt_id AS dlt_id
FROM gbif_rows g
LEFT JOIN conformed_species s
  ON s.species_natural_key = g.species_natural_key
