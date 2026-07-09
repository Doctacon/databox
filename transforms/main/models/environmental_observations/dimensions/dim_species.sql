MODEL (
  name environmental_observations.dim_species,
  kind FULL,
  description 'Conformed CDM species dimension from eBird taxonomy, GBIF occurrence taxonomy, and Xeno-canto recording metadata.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH ebird_taxonomy_ranked AS (
  SELECT
    NULLIF(LOWER(TRIM(regexp_replace(TRIM(sci_name), '\s*\([^)]*\)\s*$', ''))), '') AS species_natural_key,
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
ebird_species_list_ranked AS (
  SELECT
    species_code,
    region,
    "order"::DOUBLE AS taxonomic_order,
    _loaded_at::TIMESTAMP AS loaded_at,
    ROW_NUMBER() OVER (PARTITION BY species_code ORDER BY _loaded_at DESC) AS rn
  FROM raw_ebird.species_list
  WHERE species_code IS NOT NULL
),
ebird_species_all AS (
  SELECT
    COALESCE(t.species_natural_key, 'ebird_api:' || s.species_code) AS conformed_key,
    t.species_natural_key,
    s.species_code AS source_id,
    s.species_code,
    t.common_name,
    t.scientific_name,
    COALESCE(t.taxonomic_order, s.taxonomic_order) AS taxonomic_order,
    t.taxonomic_category,
    t.family_code,
    t.family_common_name,
    t.family_scientific_name,
    t.report_as,
    t.extinct,
    t.extinct_year,
    s.region,
    COALESCE(t.loaded_at, s.loaded_at) AS loaded_at
  FROM ebird_species_list_ranked s
  LEFT JOIN ebird_taxonomy_ranked t
    ON t.species_code = s.species_code AND t.rn = 1
  WHERE s.rn = 1

  UNION ALL

  SELECT
    COALESCE(t.species_natural_key, 'ebird_api:' || t.species_code) AS conformed_key,
    t.species_natural_key,
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
    NULL AS region,
    t.loaded_at
  FROM ebird_taxonomy_ranked t
  LEFT JOIN ebird_species_list_ranked s
    ON s.species_code = t.species_code AND s.rn = 1
  WHERE t.rn = 1 AND s.species_code IS NULL
),
ebird_species AS (
  SELECT * EXCLUDE (rn)
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY conformed_key
        ORDER BY
          CASE WHEN taxonomic_category = 'species' THEN 0 ELSE 1 END,
          loaded_at DESC NULLS LAST,
          source_id
      ) AS rn
    FROM ebird_species_all
  )
  WHERE rn = 1
),
gbif_source_rows AS (
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
gbif_ranked AS (
  SELECT
    COALESCE(
      NULLIF(LOWER(TRIM(regexp_replace(TRIM(gbif_scientific_name), '\s*\([^)]*\)\s*$', ''))), ''),
      'gbif_api:' || CAST(key AS VARCHAR)
    ) AS conformed_key,
    NULLIF(LOWER(TRIM(regexp_replace(TRIM(gbif_scientific_name), '\s*\([^)]*\)\s*$', ''))), '') AS species_natural_key,
    CASE
      WHEN NULLIF(LOWER(TRIM(regexp_replace(TRIM(gbif_scientific_name), '\s*\([^)]*\)\s*$', ''))), '') IS NULL THEN CAST(key AS VARCHAR)
      ELSE CAST(COALESCE(accepted_taxon_key, taxon_key, key) AS VARCHAR)
    END AS source_id,
    vernacular_name AS common_name,
    gbif_scientific_name AS scientific_name,
    family,
    genus,
    taxon_rank,
    taxon_key,
    accepted_taxon_key,
    _query_state_province AS region,
    _loaded_at::TIMESTAMP AS loaded_at,
    ROW_NUMBER() OVER (
      PARTITION BY COALESCE(
        NULLIF(LOWER(TRIM(regexp_replace(TRIM(gbif_scientific_name), '\s*\([^)]*\)\s*$', ''))), ''),
        'gbif_api:' || CAST(key AS VARCHAR)
      )
      ORDER BY _loaded_at DESC, key DESC
    ) AS rn
  FROM gbif_source_rows
),
gbif_species AS (
  SELECT
    conformed_key,
    species_natural_key,
    source_id,
    common_name,
    scientific_name,
    family,
    genus,
    taxon_rank,
    taxon_key,
    accepted_taxon_key,
    region,
    loaded_at
  FROM gbif_ranked
  WHERE rn = 1
),
xeno_ranked AS (
  SELECT
    COALESCE(
      CASE
        WHEN NULLIF(TRIM(genus), '') IS NOT NULL AND NULLIF(TRIM(species), '') IS NOT NULL
          THEN NULLIF(LOWER(TRIM(regexp_replace(TRIM(genus || ' ' || species), '\s*\([^)]*\)\s*$', ''))), '')
        ELSE NULL
      END,
      'xeno_canto_api:' || id
    ) AS conformed_key,
    CASE
      WHEN NULLIF(TRIM(genus), '') IS NOT NULL AND NULLIF(TRIM(species), '') IS NOT NULL
        THEN NULLIF(LOWER(TRIM(regexp_replace(TRIM(genus || ' ' || species), '\s*\([^)]*\)\s*$', ''))), '')
      ELSE NULL
    END AS species_natural_key,
    id AS source_id,
    english_name AS common_name,
    CASE
      WHEN NULLIF(TRIM(genus), '') IS NOT NULL AND NULLIF(TRIM(species), '') IS NOT NULL THEN genus || ' ' || species
      ELSE NULL
    END AS scientific_name,
    genus,
    species,
    license,
    quality,
    recording_url,
    audio_file_url,
    _loaded_at::TIMESTAMP AS loaded_at,
    COUNT(*) OVER (
      PARTITION BY COALESCE(
        CASE
          WHEN NULLIF(TRIM(genus), '') IS NOT NULL AND NULLIF(TRIM(species), '') IS NOT NULL
            THEN NULLIF(LOWER(TRIM(regexp_replace(TRIM(genus || ' ' || species), '\s*\([^)]*\)\s*$', ''))), '')
          ELSE NULL
        END,
        'xeno_canto_api:' || id
      )
    ) AS recording_count,
    ROW_NUMBER() OVER (
      PARTITION BY COALESCE(
        CASE
          WHEN NULLIF(TRIM(genus), '') IS NOT NULL AND NULLIF(TRIM(species), '') IS NOT NULL
            THEN NULLIF(LOWER(TRIM(regexp_replace(TRIM(genus || ' ' || species), '\s*\([^)]*\)\s*$', ''))), '')
          ELSE NULL
        END,
        'xeno_canto_api:' || id
      )
      ORDER BY quality ASC NULLS LAST, _loaded_at DESC, id DESC
    ) AS rn
  FROM raw_xeno_canto.recordings
  WHERE id IS NOT NULL
),
xeno_species AS (
  SELECT
    conformed_key,
    species_natural_key,
    source_id,
    common_name,
    scientific_name,
    genus,
    species,
    license,
    quality,
    recording_url,
    audio_file_url,
    loaded_at,
    recording_count
  FROM xeno_ranked
  WHERE rn = 1
),
all_keys AS (
  SELECT conformed_key FROM ebird_species
  UNION
  SELECT conformed_key FROM gbif_species
  UNION
  SELECT conformed_key FROM xeno_species
),
conformed AS (
  SELECT
    k.conformed_key,
    COALESCE(e.species_natural_key, g.species_natural_key, x.species_natural_key) AS species_natural_key,
    CASE
      WHEN e.source_id IS NOT NULL THEN 'ebird_api'
      WHEN g.source_id IS NOT NULL THEN 'gbif_api'
      ELSE 'xeno_canto_api'
    END AS source_pipeline,
    COALESCE(e.source_id, g.source_id, x.source_id) AS source_id,
    e.species_code,
    COALESCE(e.common_name, g.common_name, x.common_name) AS common_name,
    COALESCE(e.scientific_name, g.scientific_name, x.scientific_name) AS scientific_name,
    e.taxonomic_order,
    e.taxonomic_category,
    e.family_code,
    COALESCE(e.family_common_name, g.family) AS family_common_name,
    e.family_scientific_name,
    e.report_as,
    e.extinct,
    e.extinct_year,
    COALESCE(e.region, g.region) AS region,
    g.source_id AS gbif_source_id,
    g.taxon_key AS gbif_taxon_key,
    g.accepted_taxon_key AS gbif_accepted_taxon_key,
    g.family AS gbif_family,
    COALESCE(g.genus, x.genus) AS genus,
    g.taxon_rank AS gbif_taxon_rank,
    x.source_id AS xeno_canto_recording_id,
    x.recording_count AS xeno_canto_recording_count,
    x.recording_url AS xeno_canto_recording_url,
    x.audio_file_url AS xeno_canto_audio_file_url,
    x.license AS xeno_canto_license,
    x.quality AS xeno_canto_quality,
    g.source_id IS NOT NULL AS has_gbif_occurrence,
    x.source_id IS NOT NULL AS has_xeno_canto_recording,
    GREATEST(
      COALESCE(e.loaded_at, TIMESTAMP '1970-01-01'),
      COALESCE(g.loaded_at, TIMESTAMP '1970-01-01'),
      COALESCE(x.loaded_at, TIMESTAMP '1970-01-01')
    ) AS loaded_at
  FROM all_keys k
  LEFT JOIN ebird_species e
    ON e.conformed_key = k.conformed_key
  LEFT JOIN gbif_species g
    ON g.conformed_key = k.conformed_key
  LEFT JOIN xeno_species x
    ON x.conformed_key = k.conformed_key
)
SELECT
  md5('environmental_observations|species|' || conformed_key) AS species_sk,
  species_natural_key,
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
  gbif_source_id,
  gbif_taxon_key,
  gbif_accepted_taxon_key,
  gbif_family,
  genus,
  gbif_taxon_rank,
  xeno_canto_recording_id,
  xeno_canto_recording_count,
  xeno_canto_recording_url,
  xeno_canto_audio_file_url,
  xeno_canto_license,
  xeno_canto_quality,
  has_gbif_occurrence,
  has_xeno_canto_recording,
  NULLIF(loaded_at, TIMESTAMP '1970-01-01') AS loaded_at
FROM conformed

UNION ALL

SELECT
  md5('environmental_observations|species|UNKNOWN') AS species_sk,
  NULL AS species_natural_key,
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
  NULL AS gbif_source_id,
  NULL AS gbif_taxon_key,
  NULL AS gbif_accepted_taxon_key,
  NULL AS gbif_family,
  NULL AS genus,
  NULL AS gbif_taxon_rank,
  NULL AS xeno_canto_recording_id,
  NULL AS xeno_canto_recording_count,
  NULL AS xeno_canto_recording_url,
  NULL AS xeno_canto_audio_file_url,
  NULL AS xeno_canto_license,
  NULL AS xeno_canto_quality,
  FALSE AS has_gbif_occurrence,
  FALSE AS has_xeno_canto_recording,
  NULL AS loaded_at
