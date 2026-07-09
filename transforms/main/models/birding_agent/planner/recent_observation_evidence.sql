MODEL (
  name birding_agent.recent_observation_evidence,
  kind VIEW,
  description 'Planner-ready recent eBird observation evidence from the environmental observations CDM.',
  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])
);

SELECT
  md5('birding_agent|recent_observation|' || o.source_observation_id) AS observation_evidence_id,
  'ebird' AS evidence_source,
  'environmental_observations.fact_bird_observation' AS source_table,
  o.source_observation_id AS source_record_id,
  o.source_table AS raw_source_table,
  o.species_code,
  s.common_name,
  s.scientific_name,
  o.observation_datetime,
  o.observation_date,
  o.observation_count,
  o.count_display,
  o.location_id,
  o.location_name,
  o.region_code,
  o.latitude,
  o.longitude,
  o.is_valid,
  o.is_reviewed,
  o.is_notable,
  o.exotic_category,
  h.num_species_all_time AS hotspot_species_all_time,
  h.num_checklists_all_time AS hotspot_checklists_all_time,
  o.loaded_at,
  o.dlt_load_id,
  o.dlt_id
FROM environmental_observations.fact_bird_observation o
LEFT JOIN environmental_observations.dim_species s
  ON s.species_sk = o.species_sk
LEFT JOIN environmental_observations.dim_bird_hotspot h
  ON h.bird_hotspot_sk = o.bird_hotspot_sk
WHERE o.source_observation_id IS NOT NULL
