MODEL (
  name environmental_observations.fact_bird_sound_recording,
  kind FULL,
  description 'CDM fact: one row per Xeno-canto bird sound recording id; media remains externally linked.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

WITH ranked AS (
  SELECT
    *,
    CASE
      WHEN NULLIF(TRIM(genus), '') IS NOT NULL AND NULLIF(TRIM(species), '') IS NOT NULL
        THEN NULLIF(LOWER(TRIM(regexp_replace(TRIM(genus || ' ' || species), '\s*\([^)]*\)\s*$', ''))), '')
      ELSE NULL
    END AS species_natural_key,
    ROW_NUMBER() OVER (PARTITION BY id ORDER BY _loaded_at DESC) AS rn
  FROM raw_xeno_canto.recordings
  WHERE id IS NOT NULL
)
SELECT
  md5('environmental_observations|bird_sound_recording|xeno_canto_api|' || r.id) AS bird_sound_recording_sk,
  COALESCE(s.species_sk, md5('environmental_observations|species|UNKNOWN')) AS species_sk,
  'xeno_canto_api' AS source_pipeline,
  r.id AS source_id,
  r.id AS recording_id,
  r.genus,
  r.species,
  r.subspecies,
  r.group_name,
  r.english_name,
  r.recordist,
  r.country,
  r.locality,
  r.latitude::DOUBLE AS latitude,
  r.longitude::DOUBLE AS longitude,
  r.altitude,
  r.recording_type,
  r.sex,
  r.stage,
  r.method,
  r.recording_url,
  r.audio_file_url,
  r.file_name,
  r.sonogram,
  r.oscillogram,
  r.license,
  r.quality,
  r.length,
  r.recording_time,
  r.recording_date AS recording_date_text,
  TRY_CAST(r.recording_date AS DATE) AS recording_date,
  r.uploaded_at,
  r.also_species,
  r.remarks,
  r.bird_seen,
  r.animal_seen,
  r.playback_used,
  r.temperature,
  r.registration_number,
  r.automatic_recording,
  r.device,
  r.microphone,
  r._source_url AS source_url,
  r._query AS query,
  r._query_page AS query_page,
  r._loaded_at::TIMESTAMP AS loaded_at,
  r._dlt_load_id AS dlt_load_id,
  r._dlt_id AS dlt_id
FROM ranked r
LEFT JOIN environmental_observations.dim_species s
  ON s.species_natural_key = r.species_natural_key
  OR (r.species_natural_key IS NULL AND s.source_pipeline = 'xeno_canto_api' AND s.source_id = r.id)
WHERE r.rn = 1
