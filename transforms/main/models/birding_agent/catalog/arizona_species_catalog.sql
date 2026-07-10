MODEL (
  name birding_agent.arizona_species_catalog,
  kind FULL,
  description 'One row per taxon from the single latest complete eBird US-AZ snapshot, with latest complete taxonomy, exact AVONET traits, and coherent public evidence aggregates.',
  grants (
    select_ = ['staging_reader', 'domain_reader', 'analyst']
  )
);

WITH species_list_snapshots AS (
  SELECT
    _loaded_at::TIMESTAMP AS snapshot_loaded_at,
    _dlt_load_id AS snapshot_load_id
  FROM raw_ebird.species_list
  WHERE
    region = 'US-AZ'
  GROUP BY
    _loaded_at,
    _dlt_load_id
), latest_species_list_snapshot AS (
  SELECT
    snapshot_loaded_at,
    snapshot_load_id
  FROM species_list_snapshots
  ORDER BY
    snapshot_loaded_at DESC,
    snapshot_load_id DESC
  LIMIT 1
), regional_taxa AS (
  SELECT
    s.species_code,
    s.region,
    s."order"::DOUBLE AS regional_taxonomic_order,
    s._loaded_at::TIMESTAMP AS species_list_loaded_at
  FROM raw_ebird.species_list AS s
  INNER JOIN latest_species_list_snapshot AS snapshot
    ON s._loaded_at::TIMESTAMP = snapshot.snapshot_loaded_at
    AND s._dlt_load_id = snapshot.snapshot_load_id
  WHERE
    s.region = 'US-AZ' AND NOT s.species_code IS NULL
), duplicate_regional_taxa AS (
  SELECT
    species_code
  FROM regional_taxa
  GROUP BY
    species_code
  HAVING
    COUNT(*) > 1
), regional_taxa_guard AS (
  SELECT
    CASE
      WHEN COUNT(*) = 0
      THEN 1
      ELSE ERROR('Latest eBird US-AZ species-list snapshot must contain unique species codes')
    END AS is_valid
  FROM duplicate_regional_taxa
), taxonomy_snapshots AS (
  SELECT
    _loaded_at::TIMESTAMP AS snapshot_loaded_at,
    _dlt_load_id AS snapshot_load_id
  FROM raw_ebird.taxonomy
  GROUP BY
    _loaded_at,
    _dlt_load_id
), latest_taxonomy_snapshot AS (
  SELECT
    snapshot_loaded_at,
    snapshot_load_id
  FROM taxonomy_snapshots
  ORDER BY
    snapshot_loaded_at DESC,
    snapshot_load_id DESC
  LIMIT 1
), latest_taxonomy AS (
  SELECT
    t.species_code,
    t.com_name AS common_name,
    t.sci_name AS scientific_name,
    t.category AS taxonomic_category,
    t.taxon_order::DOUBLE AS taxonomy_taxonomic_order,
    t."order" AS order_name,
    t.family_code,
    t.family_com_name AS family_common_name,
    t.family_sci_name AS family_scientific_name,
    t.report_as,
    t.extinct,
    t.extinct_year,
    t._loaded_at::TIMESTAMP AS taxonomy_loaded_at
  FROM raw_ebird.taxonomy AS t
  INNER JOIN latest_taxonomy_snapshot AS snapshot
    ON t._loaded_at::TIMESTAMP = snapshot.snapshot_loaded_at
    AND t._dlt_load_id = snapshot.snapshot_load_id
  WHERE
    NOT t.species_code IS NULL
), duplicate_taxonomy AS (
  SELECT
    species_code
  FROM latest_taxonomy
  GROUP BY
    species_code
  HAVING
    COUNT(*) > 1
), taxonomy_guard AS (
  SELECT
    CASE
      WHEN COUNT(*) = 0
      THEN 1
      ELSE ERROR('Latest eBird taxonomy snapshot must contain unique species codes')
    END AS is_valid
  FROM duplicate_taxonomy
), catalog_taxa AS (
  SELECT
    r.species_code,
    r.region AS region_code,
    t.common_name,
    t.scientific_name,
    NULLIF(LOWER(TRIM(REGEXP_REPLACE(TRIM(t.scientific_name), '\s*\([^)]*\)\s*$', ''))), '') AS species_natural_key,
    t.taxonomic_category,
    COALESCE(t.taxonomy_taxonomic_order, r.regional_taxonomic_order) AS taxonomic_order,
    t.order_name,
    t.family_code,
    t.family_common_name,
    t.family_scientific_name,
    t.report_as,
    t.extinct,
    t.extinct_year,
    r.species_list_loaded_at,
    t.taxonomy_loaded_at
  FROM regional_taxa_guard AS regional_guard
  CROSS JOIN taxonomy_guard AS taxonomy_snapshot_guard
  LEFT JOIN regional_taxa AS r
    ON TRUE
  LEFT JOIN latest_taxonomy AS t
    ON t.species_code = r.species_code
  WHERE
    regional_guard.is_valid = 1
    AND taxonomy_snapshot_guard.is_valid = 1
    AND NOT r.species_code IS NULL
), conformed_species AS (
  SELECT
    *
    EXCLUDE (rn)
  FROM (
    SELECT
      species_sk,
      species_natural_key,
      ROW_NUMBER() OVER (
        PARTITION BY species_natural_key
        ORDER BY CASE WHEN source_pipeline = 'ebird_api' THEN 0 ELSE 1 END, loaded_at DESC, species_sk
      ) AS rn
    FROM environmental_observations.dim_species
    WHERE
      NOT species_natural_key IS NULL AND source_pipeline <> 'sentinel'
  )
  WHERE
    rn = 1
), public_observations AS (
  SELECT
    *
  FROM environmental_observations.fact_bird_observation
  WHERE
    region_code = 'US-AZ'
    AND NOT species_code IS NULL
    AND is_valid IS TRUE
    AND is_reviewed IS TRUE
    AND is_location_private IS FALSE
), observation_aggregates AS (
  SELECT
    species_code,
    COUNT(*)::BIGINT AS recent_public_observation_count,
    MAX(observation_datetime::TIMESTAMP) AS latest_public_observation_at,
    COUNT(DISTINCT location_id)::BIGINT AS public_location_count,
    COUNT(*) FILTER(WHERE
      is_notable IS TRUE)::BIGINT AS recent_public_notable_count,
    MAX(loaded_at::TIMESTAMP) AS ebird_observations_loaded_at
  FROM public_observations
  GROUP BY
    species_code
), public_location_rows AS (
  SELECT
    species_code,
    location_id,
    location_name,
    latitude::DOUBLE AS latitude,
    longitude::DOUBLE AS longitude,
    COUNT(*) OVER (PARTITION BY species_code, location_id)::BIGINT AS observation_count,
    MAX(observation_datetime::TIMESTAMP) OVER (PARTITION BY species_code, location_id) AS latest_observation_at,
    COUNT(*) FILTER(WHERE
      is_notable IS TRUE) OVER (PARTITION BY species_code, location_id)::BIGINT AS notable_count,
    ROW_NUMBER() OVER (
      PARTITION BY species_code, location_id
      ORDER BY observation_datetime::TIMESTAMP DESC, loaded_at::TIMESTAMP DESC, source_observation_id DESC, bird_observation_sk DESC, dlt_id DESC, location_name DESC, latitude DESC, longitude DESC
    ) AS metadata_rn
  FROM public_observations
  WHERE
    NOT location_id IS NULL
), location_aggregates AS (
  SELECT
    species_code,
    location_id,
    location_name,
    latitude,
    longitude,
    observation_count,
    latest_observation_at,
    notable_count
  FROM public_location_rows
  WHERE
    metadata_rn = 1
), ranked_locations AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY species_code
      ORDER BY observation_count DESC, latest_observation_at DESC, location_name, location_id
    ) AS location_rank
  FROM location_aggregates
), top_locations AS (
  SELECT
    species_code,
    TO_JSON(
      LIST(
        {'location_id': location_id, 'location_name': location_name, 'latitude': latitude, 'longitude': longitude, 'observation_count': observation_count, 'latest_observation_at': latest_observation_at, 'notable_count': notable_count} ORDER BY location_rank
      )
    )::TEXT AS top_public_locations_json
  FROM ranked_locations
  WHERE
    location_rank <= 10
  GROUP BY
    species_code
), gbif_aggregates AS (
  SELECT
    species_sk,
    COUNT(*)::BIGINT AS gbif_occurrence_count,
    MAX(event_date::DATE) AS gbif_latest_event_date,
    MAX(loaded_at::TIMESTAMP) AS gbif_loaded_at
  FROM environmental_observations.fact_bird_occurrence
  GROUP BY
    species_sk
), xeno_ranked AS (
  SELECT
    species_sk,
    recording_id,
    recordist,
    recording_type,
    quality,
    license,
    recording_date::DATE AS recording_date,
    loaded_at::TIMESTAMP AS loaded_at,
    ROW_NUMBER() OVER (
      PARTITION BY species_sk
      ORDER BY quality ASC, recording_date DESC, loaded_at DESC, recording_id
    ) AS rn,
    COUNT(*) OVER (PARTITION BY species_sk)::BIGINT AS xeno_canto_recording_count,
    MAX(recording_date) OVER (PARTITION BY species_sk) AS xeno_canto_latest_recording_date,
    MAX(loaded_at) OVER (PARTITION BY species_sk) AS xeno_canto_loaded_at
  FROM environmental_observations.fact_bird_sound_recording
), xeno_aggregates AS (
  SELECT
    species_sk,
    xeno_canto_recording_count,
    xeno_canto_latest_recording_date,
    recording_id AS representative_recording_id,
    recordist AS representative_recordist,
    recording_type AS representative_recording_type,
    quality AS representative_recording_quality,
    license AS representative_recording_license,
    xeno_canto_loaded_at
  FROM xeno_ranked
  WHERE
    rn = 1
)
SELECT
  MD5('birding_agent|arizona_species_catalog|' || c.species_code) AS arizona_species_catalog_id,
  c.species_code,
  c.region_code,
  c.common_name,
  c.scientific_name,
  c.species_natural_key,
  c.taxonomic_category,
  c.taxonomic_order,
  c.order_name,
  c.family_code,
  c.family_common_name,
  c.family_scientific_name,
  c.report_as,
  c.extinct,
  c.extinct_year,
  s.species_sk,
  CASE WHEN NOT t.species_natural_key IS NULL THEN 'available' ELSE 'unavailable' END AS traits_status,
  t.bird_species_traits_sk,
  t.source_scientific_name,
  t.family AS avonet_family,
  t.order_name AS avonet_order_name,
  t.avibase_id,
  t.total_individuals,
  t.female_individuals,
  t.male_individuals,
  t.unknown_sex_individuals,
  t.complete_measures,
  t.beak_length_culmen_mm,
  t.beak_length_nares_mm,
  t.beak_width_mm,
  t.beak_depth_mm,
  t.tarsus_length_mm,
  t.wing_length_mm,
  t.kipps_distance_mm,
  t.secondary_length_mm,
  t.hand_wing_index,
  t.tail_length_mm,
  t.mass_g,
  t.mass_source,
  t.mass_reference_other,
  t.inference,
  t.traits_inferred,
  t.reference_species,
  t.habitat,
  t.habitat_density_code,
  t.habitat_density_label,
  t.migration_code,
  t.migration_label,
  t.trophic_level,
  t.trophic_niche,
  t.primary_lifestyle,
  t.dataset_doi,
  t.dataset_version,
  t.dataset_license,
  t.source_file_id,
  t.source_file_md5,
  t.source_url AS avonet_source_url,
  t.loaded_at AS avonet_loaded_at,
  t.dlt_load_id AS avonet_dlt_load_id,
  t.dlt_id AS avonet_dlt_id,
  COALESCE(o.recent_public_observation_count, 0)::BIGINT AS recent_public_observation_count,
  o.latest_public_observation_at,
  COALESCE(o.public_location_count, 0)::BIGINT AS public_location_count,
  COALESCE(o.recent_public_notable_count, 0)::BIGINT AS recent_public_notable_count,
  l.top_public_locations_json,
  COALESCE(g.gbif_occurrence_count, 0)::BIGINT AS gbif_occurrence_count,
  g.gbif_latest_event_date,
  COALESCE(x.xeno_canto_recording_count, 0)::BIGINT AS xeno_canto_recording_count,
  x.xeno_canto_latest_recording_date,
  x.representative_recording_id,
  x.representative_recordist,
  x.representative_recording_type,
  x.representative_recording_quality,
  x.representative_recording_license,
  c.species_list_loaded_at,
  c.taxonomy_loaded_at,
  o.ebird_observations_loaded_at,
  g.gbif_loaded_at,
  x.xeno_canto_loaded_at,
  NULLIF(
    GREATEST(
      COALESCE(c.species_list_loaded_at::TIMESTAMP, '1970-01-01'::TIMESTAMP),
      COALESCE(c.taxonomy_loaded_at::TIMESTAMP, '1970-01-01'::TIMESTAMP),
      COALESCE(o.ebird_observations_loaded_at::TIMESTAMP, '1970-01-01'::TIMESTAMP),
      COALESCE(t.loaded_at::TIMESTAMP, '1970-01-01'::TIMESTAMP),
      COALESCE(g.gbif_loaded_at::TIMESTAMP, '1970-01-01'::TIMESTAMP),
      COALESCE(x.xeno_canto_loaded_at::TIMESTAMP, '1970-01-01'::TIMESTAMP)
    ),
    '1970-01-01'::TIMESTAMP
  ) AS catalog_freshness_at
FROM catalog_taxa AS c
LEFT JOIN conformed_species AS s
  ON s.species_natural_key = c.species_natural_key
LEFT JOIN environmental_observations.dim_bird_species_traits AS t
  ON t.species_natural_key = c.species_natural_key
LEFT JOIN observation_aggregates AS o
  ON o.species_code = c.species_code
LEFT JOIN top_locations AS l
  ON l.species_code = c.species_code
LEFT JOIN gbif_aggregates AS g
  ON g.species_sk = s.species_sk
LEFT JOIN xeno_aggregates AS x
  ON x.species_sk = s.species_sk
ORDER BY
  c.taxonomic_order,
  c.species_code
