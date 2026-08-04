MODEL (
  name rufous_public.inaturalist_commercial_image,
  kind FULL,
  description 'Strictly commercial-use iNaturalist taxon-photo candidates for catalog species without an approved image, selected from the latest internally coherent complete snapshot.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH candidate_validation AS (
  SELECT
    candidates.*,
    species.identity_status,
    species.taxon_id AS species_taxon_id,
    species.target_common_name AS species_common_name,
    species.target_scientific_name AS species_scientific_name,
    CASE
      WHEN candidates.photo_id::BIGINT > 0
        AND candidates.taxon_id::BIGINT > 0
        AND candidates.taxon_id::BIGINT = species.taxon_id::BIGINT
        AND LOWER(TRIM(COALESCE(species.identity_status, ''))) = 'exact_active_species'
        AND TRIM(candidates.target_common_name) = TRIM(species.target_common_name)
        AND TRIM(candidates.target_scientific_name) = TRIM(species.target_scientific_name)
        AND REGEXP_FULL_MATCH(
          TRIM(candidates.source_page_url),
          'https://www\.inaturalist\.org/photos/' || candidates.photo_id::VARCHAR
        )
        AND REGEXP_FULL_MATCH(
          LOWER(TRIM(candidates.source_image_original_url)),
          'https://inaturalist-open-data\.s3\.amazonaws\.com/photos/'
          || candidates.photo_id::VARCHAR
          || '/original\.(?:jpg|jpeg|png|webp)'
        )
        AND REGEXP_FULL_MATCH(
          LOWER(TRIM(candidates.source_image_large_url)),
          'https://inaturalist-open-data\.s3\.amazonaws\.com/photos/'
          || candidates.photo_id::VARCHAR
          || '/large\.(?:jpg|jpeg|png|webp)'
        )
        AND (
          (
            TRIM(candidates.license_code) = 'CC0 1.0'
            AND TRIM(candidates.license_url) =
              'https://creativecommons.org/publicdomain/zero/1.0/'
          ) OR (
            TRIM(candidates.license_code) = 'CC BY 4.0'
            AND TRIM(candidates.license_url) =
              'https://creativecommons.org/licenses/by/4.0/'
          ) OR (
            TRIM(candidates.license_code) = 'CC BY-SA 4.0'
            AND TRIM(candidates.license_url) =
              'https://creativecommons.org/licenses/by-sa/4.0/'
          )
        )
        AND NULLIF(TRIM(candidates.creator), '') IS NOT NULL
        AND LENGTH(TRIM(candidates.creator)) BETWEEN 2 AND 200
        AND REGEXP_MATCHES(candidates.creator, '[[:alpha:]]')
        AND NOT REGEXP_MATCHES(candidates.creator, '[<>[:cntrl:]]')
        AND NOT REGEXP_MATCHES(
          LOWER(TRIM(candidates.creator)),
          '(^|[^a-z])(anonymous|unknown)([^a-z]|$)'
        )
        AND LOWER(TRIM(candidates.creator)) NOT IN (
          'author unknown',
          'inat staff',
          'inaturalist'
        )
        AND candidates.original_width::BIGINT > 0
        AND candidates.original_height::BIGINT > 0
        AND GREATEST(
          candidates.original_width::BIGINT,
          candidates.original_height::BIGINT
        ) BETWEEN 1000 AND 100000
        AND LEAST(
          candidates.original_width::BIGINT,
          candidates.original_height::BIGINT
        ) >= 750
        AND candidates.original_width::BIGINT * candidates.original_height::BIGINT
          <= 50000000
        AND candidates.curated_position::BIGINT BETWEEN 1 AND 20
        AND candidates.curated_position::BIGINT
          <= species.curated_photos_inspected::BIGINT
        AND candidates._loaded_at IS NOT NULL
      THEN 1
      ELSE 0
    END AS is_strict_candidate
  FROM raw_inaturalist.photo_candidates AS candidates
  LEFT JOIN raw_inaturalist.photo_species_results AS species
    ON candidates.run_id = species.run_id
    AND candidates.species_code = species.species_code
),
candidate_counts AS (
  SELECT
    run_id,
    COUNT(*) AS candidate_row_count,
    COUNT(DISTINCT (species_code, photo_id)) AS distinct_candidate_count,
    COUNT(DISTINCT (species_code, curated_position)) AS distinct_position_count,
    SUM(is_strict_candidate) AS strict_candidate_count
  FROM candidate_validation
  GROUP BY run_id
),
candidate_species_counts AS (
  SELECT
    run_id,
    species_code,
    COUNT(*) AS candidate_row_count,
    COUNT(DISTINCT photo_id) AS distinct_candidate_count
  FROM raw_inaturalist.photo_candidates
  GROUP BY run_id, species_code
),
species_validation AS (
  SELECT
    species.*,
    COALESCE(candidates.candidate_row_count, 0) AS persisted_candidate_count,
    COALESCE(candidates.distinct_candidate_count, 0) AS distinct_candidate_count,
    CASE
      WHEN NULLIF(TRIM(species.species_code), '') IS NOT NULL
        AND REGEXP_FULL_MATCH(TRIM(species.species_code), '[A-Za-z0-9][A-Za-z0-9_.-]{0,63}')
        AND NULLIF(TRIM(species.target_common_name), '') IS NOT NULL
        AND LENGTH(TRIM(species.target_common_name)) <= 200
        AND NOT REGEXP_MATCHES(species.target_common_name, '[<>[:cntrl:]]')
        AND NULLIF(TRIM(species.target_scientific_name), '') IS NOT NULL
        AND LENGTH(TRIM(species.target_scientific_name)) <= 200
        AND NOT REGEXP_MATCHES(species.target_scientific_name, '[<>[:cntrl:]]')
        AND REGEXP_FULL_MATCH(
          TRIM(species.target_scientific_name),
          '[A-Z][A-Za-z-]+ [a-z][A-Za-z-]+'
        )
        AND LOWER(TRIM(COALESCE(species.identity_status, ''))) IN (
          'exact_active_species',
          'unavailable'
        )
        AND (
          (
            LOWER(TRIM(species.identity_status)) = 'exact_active_species'
            AND species.taxon_id::BIGINT > 0
          ) OR (
            LOWER(TRIM(species.identity_status)) = 'unavailable'
            AND species.eligible_candidate_count::BIGINT = 0
          )
        )
        AND species.curated_photo_count::BIGINT >= 0
        AND species.curated_photos_inspected::BIGINT BETWEEN 0 AND 20
        AND species.curated_photos_inspected::BIGINT
          <= species.curated_photo_count::BIGINT
        AND species.eligible_candidate_count::BIGINT >= 0
        AND species.eligible_candidate_count::BIGINT
          = COALESCE(candidates.candidate_row_count, 0)
        AND COALESCE(candidates.candidate_row_count, 0)
          = COALESCE(candidates.distinct_candidate_count, 0)
        AND species._loaded_at IS NOT NULL
      THEN 1
      ELSE 0
    END AS is_coherent_species
  FROM raw_inaturalist.photo_species_results AS species
  LEFT JOIN candidate_species_counts AS candidates
    ON species.run_id = candidates.run_id
    AND species.species_code = candidates.species_code
),
species_counts AS (
  SELECT
    run_id,
    COUNT(*) AS species_row_count,
    COUNT(DISTINCT species_code) AS distinct_species_count,
    SUM(is_coherent_species) AS coherent_species_count,
    SUM(
      CASE
        WHEN LOWER(TRIM(identity_status)) = 'exact_active_species' THEN 1
        ELSE 0
      END
    ) AS exact_species_count,
    SUM(
      CASE WHEN eligible_candidate_count::BIGINT > 0 THEN 1 ELSE 0 END
    ) AS species_with_candidates,
    SUM(curated_photos_inspected::BIGINT) AS curated_photos_inspected,
    SUM(eligible_candidate_count::BIGINT) AS eligible_candidate_count
  FROM species_validation
  GROUP BY run_id
),
complete_runs AS (
  SELECT
    runs.run_id,
    ROW_NUMBER() OVER (
      ORDER BY runs.completed_at DESC, runs._loaded_at DESC, runs.run_id DESC
    ) AS run_rank
  FROM raw_inaturalist.photo_discovery_runs AS runs
  INNER JOIN species_counts AS species
    ON runs.run_id = species.run_id
  LEFT JOIN candidate_counts AS candidates
    ON runs.run_id = candidates.run_id
  WHERE LOWER(TRIM(COALESCE(runs.status, ''))) = 'complete'
    AND runs.target_species_count::BIGINT > 0
    AND runs.target_species_count::BIGINT = species.species_row_count
    AND species.species_row_count = species.distinct_species_count
    AND species.species_row_count = species.coherent_species_count
    AND runs.exact_species_count::BIGINT = species.exact_species_count
    AND runs.species_with_candidates::BIGINT = species.species_with_candidates
    AND runs.curated_photos_inspected::BIGINT = species.curated_photos_inspected
    AND runs.eligible_candidate_count::BIGINT = species.eligible_candidate_count
    AND runs.eligible_candidate_count::BIGINT
      = COALESCE(candidates.candidate_row_count, 0)
    AND COALESCE(candidates.candidate_row_count, 0)
      = COALESCE(candidates.distinct_candidate_count, 0)
    AND COALESCE(candidates.candidate_row_count, 0)
      = COALESCE(candidates.distinct_position_count, 0)
    AND COALESCE(candidates.candidate_row_count, 0)
      = COALESCE(candidates.strict_candidate_count, 0)
    AND runs.max_curated_photos::BIGINT BETWEEN 1 AND 20
    AND runs.request_max_attempts::BIGINT BETWEEN 1 AND 3
    AND runs.request_count::BIGINT
      >= runs.target_species_count::BIGINT + runs.exact_species_count::BIGINT
    AND runs.started_at IS NOT NULL
    AND runs.completed_at IS NOT NULL
    AND runs._loaded_at IS NOT NULL
),
latest_complete AS (
  SELECT run_id
  FROM complete_runs
  WHERE run_rank = 1
),
eligible AS (
  SELECT candidates.*
  FROM candidate_validation AS candidates
  INNER JOIN latest_complete AS snapshot
    ON candidates.run_id = snapshot.run_id
  WHERE candidates.is_strict_candidate = 1
)
SELECT
  TRIM(species_code) AS species_code,
  TRIM(target_common_name) AS common_name,
  TRIM(target_scientific_name) AS scientific_name,
  TRIM(source_page_url) AS source_page_url,
  TRIM(source_image_original_url) AS source_image_url,
  TRIM(creator) AS creator,
  TRIM(license_code) AS license,
  TRIM(target_common_name) || ' photograph' AS title,
  'Curated iNaturalist taxon photograph of '
    || TRIM(target_common_name)
    || ' by '
    || TRIM(creator)
    || '.' AS caption,
  TRIM(target_common_name) || ' photographed by ' || TRIM(creator) AS alt_text,
  CAST(NULL AS DATE) AS source_published_at,
  original_width::BIGINT AS source_width,
  original_height::BIGINT AS source_height,
  CASE
    WHEN LOWER(source_image_original_url) LIKE '%.png' THEN 'image/png'
    WHEN LOWER(source_image_original_url) LIKE '%.webp' THEN 'image/webp'
    ELSE 'image/jpeg'
  END AS mime_type,
  'inaturalist_exact_active_species_curated_taxon_photo' AS discovery_method,
  _loaded_at::TIMESTAMP AS loaded_at
FROM eligible
;
