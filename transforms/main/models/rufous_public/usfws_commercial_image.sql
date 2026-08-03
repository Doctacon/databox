MODEL (
  name rufous_public.usfws_commercial_image,
  kind FULL,
  description 'Commercial-use USFWS bird images from the latest complete caller-owned species snapshot; exact scientific tags, safe FWS URLs, usable credits, fail-closed licenses, and official restricted marks excluded.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH persisted_records AS (
  SELECT
    run_id,
    COUNT(DISTINCT (species_code, source_page_url)) AS persisted_record_count
  FROM raw_usfws.image_records
  WHERE NULLIF(TRIM(species_code), '') IS NOT NULL
    AND NULLIF(TRIM(source_page_url), '') IS NOT NULL
  GROUP BY run_id
),
complete_runs AS (
  SELECT
    runs.run_id,
    ROW_NUMBER() OVER (
      ORDER BY runs.completed_at DESC, runs._loaded_at DESC, runs.run_id DESC
    ) AS run_rank
  FROM raw_usfws.image_search_runs AS runs
  LEFT JOIN persisted_records AS persisted
    ON runs.run_id = persisted.run_id
  WHERE LOWER(TRIM(COALESCE(runs.status, ''))) = 'complete'
    AND runs.target_species_count = runs.completed_target_species_count
    AND runs.record_count = COALESCE(persisted.persisted_record_count, 0)
    AND runs.completed_at IS NOT NULL
),
latest_complete AS (
  SELECT run_id
  FROM complete_runs
  WHERE run_rank = 1
),
normalized AS (
  SELECT
    records.*,
    LOWER(
      TRIM(
        REGEXP_REPLACE(
          LOWER(COALESCE(records.source_license, '')),
          '[^a-z0-9]+',
          ' ',
          'g'
        )
      )
    ) AS normalized_license,
    LOWER(TRIM(COALESCE(records.source_license_url, ''))) AS normalized_license_url,
    TRY(
      URL_DECODE(
        SPLIT_PART(
          SUBSTRING(
            TRIM(records.source_image_medium_url),
            LENGTH('https://www.fws.gov') + 1
          ),
          '?',
          1
        )
      )
    ) AS decoded_image_path,
    ROW_NUMBER() OVER (
      PARTITION BY records.species_code, records.source_page_url
      ORDER BY records._loaded_at DESC, records.media_id DESC
    ) AS record_rank
  FROM raw_usfws.image_records AS records
  INNER JOIN latest_complete AS snapshot
    ON records.run_id = snapshot.run_id
),
rights_semantics AS (
  SELECT
    *,
    CASE
      WHEN normalized_license = 'public domain' THEN 'public-domain'
      WHEN normalized_license IN (
        'cc0',
        'cc0 1 0',
        'cc0 1 0 universal',
        'creative commons zero 1 0',
        'creative commons zero 1 0 universal',
        'creative commons cc0 1 0',
        'creative commons cc0 1 0 universal'
      ) OR REGEXP_FULL_MATCH(
        LOWER(TRIM(source_license)),
        'https?://(?:www\.)?creativecommons\.org/publicdomain/zero/1\.0/(?:legalcode/?)?'
      ) THEN 'cc0-1.0'
      WHEN normalized_license IN (
        'cc by 1 0',
        'creative commons attribution 1 0'
      ) THEN 'cc-by-1.0'
      WHEN normalized_license IN (
        'cc by 2 0',
        'creative commons attribution 2 0'
      ) THEN 'cc-by-2.0'
      WHEN normalized_license IN (
        'cc by 2 5',
        'creative commons attribution 2 5'
      ) THEN 'cc-by-2.5'
      WHEN normalized_license IN (
        'cc by 3 0',
        'creative commons attribution 3 0'
      ) THEN 'cc-by-3.0'
      WHEN normalized_license IN (
        'cc by 4 0',
        'creative commons attribution 4 0'
      ) THEN 'cc-by-4.0'
      WHEN normalized_license IN (
        'cc by sa 1 0',
        'creative commons attribution sharealike 1 0'
      ) THEN 'cc-by-sa-1.0'
      WHEN normalized_license IN (
        'cc by sa 2 0',
        'creative commons attribution sharealike 2 0'
      ) THEN 'cc-by-sa-2.0'
      WHEN normalized_license IN (
        'cc by sa 2 5',
        'creative commons attribution sharealike 2 5'
      ) THEN 'cc-by-sa-2.5'
      WHEN normalized_license IN (
        'cc by sa 3 0',
        'creative commons attribution sharealike 3 0'
      ) THEN 'cc-by-sa-3.0'
      WHEN normalized_license IN (
        'cc by sa 4 0',
        'creative commons attribution sharealike 4 0'
      ) THEN 'cc-by-sa-4.0'
      WHEN REGEXP_FULL_MATCH(
        LOWER(TRIM(source_license)),
        'https?://(?:www\.)?creativecommons\.org/licenses/by/(?:1\.0|2\.0|2\.5|3\.0|4\.0)/(?:legalcode/?)?'
      ) THEN 'cc-by-' || REGEXP_EXTRACT(
        LOWER(TRIM(source_license)),
        '/licenses/by/(1\.0|2\.0|2\.5|3\.0|4\.0)/',
        1
      )
      WHEN REGEXP_FULL_MATCH(
        LOWER(TRIM(source_license)),
        'https?://(?:www\.)?creativecommons\.org/licenses/by-sa/(?:1\.0|2\.0|2\.5|3\.0|4\.0)/(?:legalcode/?)?'
      ) THEN 'cc-by-sa-' || REGEXP_EXTRACT(
        LOWER(TRIM(source_license)),
        '/licenses/by-sa/(1\.0|2\.0|2\.5|3\.0|4\.0)/',
        1
      )
    END AS license_semantics,
    CASE
      WHEN REGEXP_FULL_MATCH(
        normalized_license_url,
        'https://(?:www\.)?fws\.gov/notices/?'
      ) THEN 'public-domain'
      WHEN REGEXP_FULL_MATCH(
        normalized_license_url,
        'https?://(?:www\.)?creativecommons\.org/publicdomain/zero/1\.0/(?:legalcode/?)?'
      ) THEN 'cc0-1.0'
      WHEN REGEXP_FULL_MATCH(
        normalized_license_url,
        'https?://(?:www\.)?creativecommons\.org/licenses/by/(?:1\.0|2\.0|2\.5|3\.0|4\.0)/(?:legalcode/?)?'
      ) THEN 'cc-by-' || REGEXP_EXTRACT(
        normalized_license_url,
        '/licenses/by/(1\.0|2\.0|2\.5|3\.0|4\.0)/',
        1
      )
      WHEN REGEXP_FULL_MATCH(
        normalized_license_url,
        'https?://(?:www\.)?creativecommons\.org/licenses/by-sa/(?:1\.0|2\.0|2\.5|3\.0|4\.0)/(?:legalcode/?)?'
      ) THEN 'cc-by-sa-' || REGEXP_EXTRACT(
        normalized_license_url,
        '/licenses/by-sa/(1\.0|2\.0|2\.5|3\.0|4\.0)/',
        1
      )
    END AS license_url_semantics
  FROM normalized
),
restricted_mark_evidence AS (
  SELECT
    *,
    TRIM(
      REGEXP_REPLACE(
        LOWER(
          CONCAT_WS(
            ' ',
            COALESCE(source_title, ''),
            COALESCE(search_result_title, ''),
            COALESCE(source_caption, ''),
            COALESCE(search_result_caption, ''),
            COALESCE(source_alt_text, ''),
            COALESCE(search_result_alt_text, ''),
            COALESCE(subject_tags_json, ''),
            COALESCE(
              TRY(URL_DECODE(TRY(URL_DECODE(source_page_url)))),
              TRY(URL_DECODE(source_page_url)),
              source_page_url,
              ''
            ),
            COALESCE(
              TRY(URL_DECODE(TRY(URL_DECODE(source_image_medium_url)))),
              TRY(URL_DECODE(source_image_medium_url)),
              source_image_medium_url,
              ''
            ),
            COALESCE(
              TRY(URL_DECODE(TRY(URL_DECODE(source_image_original_url)))),
              TRY(URL_DECODE(source_image_original_url)),
              source_image_original_url,
              ''
            ),
            COALESCE(
              TRY(URL_DECODE(TRY(URL_DECODE(search_result_image_url)))),
              TRY(URL_DECODE(search_result_image_url)),
              search_result_image_url,
              ''
            )
          )
        ),
        '[^a-z0-9]+',
        ' ',
        'g'
      )
    ) AS normalized_mark_evidence
  FROM rights_semantics
),
restricted_mark_classification AS (
  SELECT
    *,
    CASE
      WHEN REGEXP_MATCHES(
        normalized_mark_evidence,
        '(^| )(logos?|logo ?mark|word ?mark|brand ?mark)( |$)'
      ) OR REGEXP_MATCHES(
        normalized_mark_evidence,
        '(^| )(agency|doi|fws|official|service|usfws) seal( |$)'
      ) OR REGEXP_MATCHES(
        normalized_mark_evidence,
        '(^| )(department( of( the)?)? interior|fish( and)? wildlife( service)?|us fish and wildlife( service)?) seal( |$)'
      ) THEN 'service_or_agency_logo_or_seal'
      WHEN REGEXP_MATCHES(
        normalized_mark_evidence,
        '(^| )(duck ?stamps?|federal migratory bird hunting and conservation stamp|migratory bird hunting and conservation stamp)( |$)'
      ) THEN 'federal_or_junior_duck_stamp'
      WHEN REGEXP_MATCHES(
        normalized_mark_evidence,
        '(^| )federal aid( in)? (wildlife|sport fish) restoration( |$)'
      ) OR (
        REGEXP_MATCHES(
          normalized_mark_evidence,
          '(^| )(emblems?|insignia|logos?|marks?|symbols?)( |$)'
        )
        AND REGEXP_MATCHES(
          normalized_mark_evidence,
          '(^| )(dingell johnson|pittman robertson|sport fish restoration|wallop breaux|wildlife( and)? sport fish restoration|wildlife restoration|wsfr)( |$)'
        )
      ) THEN 'federal_aid_restoration_symbol'
      WHEN REGEXP_MATCHES(
        normalized_mark_evidence,
        '(^| )(blue goose (refuge|sign)|national wildlife refuge system (blue goose|symbol)|refuge system blue goose)( |$)'
      ) OR (
        REGEXP_MATCHES(normalized_mark_evidence, '(^| )blue goose( |$)')
        AND (
          REGEXP_MATCHES(
            normalized_mark_evidence,
            '(^| )(emblems?|insignia|logos?|marks?|symbols?)( |$)'
          )
          OR REGEXP_MATCHES(
            normalized_mark_evidence,
            '(^| )national wildlife refuge system( |$)'
          )
        )
      ) THEN 'blue_goose_refuge_mark'
    END AS restricted_mark_reason
  FROM restricted_mark_evidence
),
eligible AS (
  SELECT *
  FROM restricted_mark_classification
  WHERE record_rank = 1
    AND LOWER(TRIM(COALESCE(detail_fetch_status, ''))) = 'ok'
    AND NULLIF(TRIM(species_code), '') IS NOT NULL
    AND NULLIF(TRIM(target_common_name), '') IS NOT NULL
    AND NULLIF(TRIM(target_scientific_name), '') IS NOT NULL
    AND COALESCE(
      LIST_CONTAINS(
        TRY(FROM_JSON(scientific_name_tags_json, '["VARCHAR"]')),
        TRIM(target_scientific_name)
      ),
      FALSE
    )
    AND REGEXP_FULL_MATCH(
      TRIM(source_page_url),
      'https://www\.fws\.gov/media/[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?'
    )
    AND REGEXP_FULL_MATCH(
      TRIM(source_image_medium_url),
      'https://www\.fws\.gov/sites/default/files/[A-Za-z0-9._~%()/+@,-]+\.(?:[Jj][Pp][Gg]|[Jj][Pp][Ee][Gg]|[Pp][Nn][Gg]|[Ww][Ee][Bb][Pp])(?:\?itok=[A-Za-z0-9_-]{1,128})?'
    )
    AND decoded_image_path IS NOT NULL
    AND STARTS_WITH(decoded_image_path, '/sites/default/files/')
    AND STRPOS(decoded_image_path, CHR(92)) = 0
    AND STRPOS(decoded_image_path, '//') = 0
    AND NOT REGEXP_MATCHES(decoded_image_path, '(^|/)\.{1,2}(/|$)')
    AND NOT REGEXP_MATCHES(decoded_image_path, '[[:cntrl:]]')
    AND LOWER(TRIM(COALESCE(source_media_type, ''))) = 'image'
    AND LOWER(TRIM(COALESCE(source_mime_type, ''))) IN (
      'image/jpeg',
      'image/jpg',
      'image/png',
      'image/webp'
    )
    AND source_image_medium_width::BIGINT > 0
    AND source_image_medium_height::BIGINT > 0
    AND source_image_medium_width::BIGINT * source_image_medium_height::BIGINT <= 50000000
    AND NULLIF(
      TRIM(COALESCE(source_title, search_result_title, '')),
      ''
    ) IS NOT NULL
    AND LENGTH(TRIM(COALESCE(source_title, search_result_title, ''))) <= 500
    AND NOT REGEXP_MATCHES(
      COALESCE(source_title, search_result_title, ''),
      '[[:cntrl:]]'
    )
    AND NULLIF(
      TRIM(
        COALESCE(
          source_alt_text,
          search_result_alt_text,
          source_caption,
          source_title,
          ''
        )
      ),
      ''
    ) IS NOT NULL
    AND LENGTH(
      TRIM(
        COALESCE(
          source_alt_text,
          search_result_alt_text,
          source_caption,
          source_title,
          ''
        )
      )
    ) <= 1000
    AND NOT REGEXP_MATCHES(
      COALESCE(
        source_alt_text,
        search_result_alt_text,
        source_caption,
        source_title,
        ''
      ),
      '[[:cntrl:]]'
    )
    AND LENGTH(TRIM(COALESCE(source_caption, search_result_caption, ''))) <= 2000
    AND NULLIF(TRIM(discovery_method), '') IS NOT NULL
    AND _loaded_at IS NOT NULL
    AND NULLIF(TRIM(source_creator), '') IS NOT NULL
    AND LENGTH(TRIM(source_creator)) BETWEEN 2 AND 200
    AND NOT REGEXP_MATCHES(source_creator, '[<>[:cntrl:]]')
    AND REGEXP_MATCHES(source_creator, '[[:alpha:]]')
    AND LOWER(TRIM(source_creator)) NOT IN (
      'unknown',
      'n/a',
      'na',
      'none',
      'null',
      'anonymous',
      'public domain',
      'copyrighted'
    )
    AND LOWER(TRIM(source_creator)) <> LOWER(TRIM(target_common_name))
    AND LOWER(TRIM(source_creator)) <> LOWER(TRIM(target_scientific_name))
    AND LOWER(TRIM(source_creator)) <> LOWER(TRIM(COALESCE(source_title, '')))
    AND LOWER(TRIM(source_creator)) <> LOWER(TRIM(COALESCE(source_caption, '')))
    AND license_semantics IS NOT NULL
    AND (
      NULLIF(TRIM(source_license_url), '') IS NULL
      OR license_url_semantics = license_semantics
    )
    AND restricted_mark_reason IS NULL
)
SELECT
  TRIM(species_code) AS species_code,
  TRIM(target_common_name) AS common_name,
  TRIM(target_scientific_name) AS scientific_name,
  TRIM(source_page_url) AS source_page_url,
  TRIM(source_image_medium_url) AS source_image_url,
  TRIM(source_creator) AS creator,
  TRIM(source_license) AS license,
  COALESCE(
    NULLIF(TRIM(source_title), ''),
    NULLIF(TRIM(search_result_title), '')
  ) AS title,
  COALESCE(
    NULLIF(TRIM(source_caption), ''),
    NULLIF(TRIM(search_result_caption), '')
  ) AS caption,
  COALESCE(
    NULLIF(TRIM(source_alt_text), ''),
    NULLIF(TRIM(search_result_alt_text), ''),
    NULLIF(TRIM(source_caption), ''),
    NULLIF(TRIM(source_title), '')
  ) AS alt_text,
  TRY_CAST(
    COALESCE(
      NULLIF(TRIM(source_published_at), ''),
      NULLIF(TRIM(search_result_published_at), '')
    ) AS DATE
  ) AS source_published_at,
  source_image_medium_width::BIGINT AS source_width,
  source_image_medium_height::BIGINT AS source_height,
  NULLIF(TRIM(source_mime_type), '') AS mime_type,
  TRIM(discovery_method) AS discovery_method,
  _loaded_at::TIMESTAMP AS loaded_at
FROM eligible
;
