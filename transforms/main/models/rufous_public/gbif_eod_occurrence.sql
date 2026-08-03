MODEL (
  name rufous_public.gbif_eod_occurrence,
  kind FULL,
  description 'Sanitized Arizona occurrence projection from the CC BY GBIF EOD dataset; no observer, locality, checklist, or direct-eBird fields.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH eligible AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY key ORDER BY _loaded_at DESC, _dlt_id DESC) AS rn
  FROM raw_gbif.occurrences
  WHERE key IS NOT NULL
    AND dataset_key = '4fa7b334-ce0d-4e88-aaae-2e0c138d049e'
    AND UPPER(TRIM(COALESCE(country_code, ''))) = 'US'
    AND LOWER(TRIM(COALESCE(state_province, ''))) = 'arizona'
    AND UPPER(TRIM(COALESCE(occurrence_status, ''))) = 'PRESENT'
    AND decimal_latitude BETWEEN 31.0 AND 37.1
    AND decimal_longitude BETWEEN -115.0 AND -109.0
    AND TRY_CAST(event_date AS DATE) IS NOT NULL
    AND LOWER(TRIM(COALESCE(license, ''))) IN (
      'cc by 4.0',
      'cc-by 4.0',
      'cc-by-4.0',
      'https://creativecommons.org/licenses/by/4.0',
      'https://creativecommons.org/licenses/by/4.0/',
      'http://creativecommons.org/licenses/by/4.0',
      'http://creativecommons.org/licenses/by/4.0/',
      'https://creativecommons.org/licenses/by/4.0/legalcode',
      'http://creativecommons.org/licenses/by/4.0/legalcode'
    )
)
SELECT
  CAST(key AS VARCHAR) AS source_id,
  key AS gbif_key,
  COALESCE(NULLIF(TRIM(gbif_id), ''), CAST(key AS VARCHAR)) AS gbif_id,
  dataset_key,
  COALESCE(NULLIF(TRIM(dataset_title), ''), 'EOD – eBird Observation Dataset') AS dataset_title,
  COALESCE(NULLIF(TRIM(dataset_publisher), ''), 'Cornell Lab of Ornithology') AS dataset_publisher,
  COALESCE(
    NULLIF(TRIM(dataset_citation), ''),
    'Imani J, Audette C, Auer T, Barker S, Barry J, Charnoky M, Crowley C, Curtis J, Davies I, Davis C, Diaz R, Feinberg A, Fink D, Ganger J, Garrett J, Gerbracht J, Hanks C, Hayes M, Hochachka W, Iliff M, Jordan A, Ligocki S, Long T, Morris W, Morrow S, Oldham L, Padilla Obregon F, Robinson O, Rodewald A, Ruiz-Gutierrez V, Schloss M, Smith A, Smith J, Stillman A, Stokowski M, Strimas-Mackey M, Sullivan B, Tedeschi A, Weber D, Wolf H, Wood C (2025). EOD – eBird Observation Dataset. Cornell Lab of Ornithology. Occurrence dataset https://doi.org/10.15468/aomfnb accessed via GBIF.org.'
  ) AS dataset_citation,
  COALESCE(NULLIF(TRIM(dataset_doi), ''), '10.15468/aomfnb') AS dataset_doi,
  COALESCE(
    NULLIF(TRIM(dataset_source_url), ''),
    'https://www.gbif.org/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e'
  ) AS dataset_source_url,
  COALESCE(
    NULLIF(TRIM(dataset_license), ''),
    'https://creativecommons.org/licenses/by/4.0/'
  ) AS dataset_license,
  COALESCE(
    NULLIF(TRIM(species), ''),
    NULLIF(TRIM(accepted_scientific_name), ''),
    NULLIF(TRIM(scientific_name), '')
  ) AS scientific_name,
  NULLIF(TRIM(accepted_scientific_name), '') AS accepted_scientific_name,
  NULLIF(TRIM(vernacular_name), '') AS common_name,
  NULLIF(TRIM(taxon_rank), '') AS taxon_rank,
  NULLIF(TRIM(family), '') AS family,
  NULLIF(TRIM(order_name), '') AS order_name,
  accepted_taxon_key,
  taxon_key,
  species_key,
  TRY_CAST(event_date AS DATE) AS event_date,
  CAST(TRY_CAST(event_date AS DATE) AS VARCHAR) AS event_date_text,
  ROUND(decimal_latitude::DOUBLE, 2) AS latitude,
  ROUND(decimal_longitude::DOUBLE, 2) AS longitude,
  GREATEST(COALESCE(coordinate_uncertainty_in_meters::DOUBLE, 0), 1000.0)
    AS coordinate_uncertainty_in_meters,
  NULLIF(TRIM(basis_of_record), '') AS basis_of_record,
  'PRESENT' AS occurrence_status,
  license,
  'https://www.gbif.org/occurrence/' || CAST(key AS VARCHAR) AS source_reference_url,
  _loaded_at::TIMESTAMP AS loaded_at
FROM eligible
WHERE rn = 1
  AND COALESCE(
    NULLIF(TRIM(species), ''),
    NULLIF(TRIM(accepted_scientific_name), ''),
    NULLIF(TRIM(scientific_name), '')
  ) IS NOT NULL
;
