export type JsonObject = Record<string, unknown>;

export interface ApiError {
  error: { code: string; message: string };
}

export interface PlanSummary {
  trip_plan_id: string;
  requested_location: string;
  normalized_location_name: string | null;
  window_start: string;
  window_end: string;
  duration_minutes: number;
  plan_status: string;
  caveats: string[];
  created_at: string;
  updated_at: string;
}

export interface TripPlan extends PlanSummary {
  latitude: number | null;
  longitude: number | null;
  region_code: string | null;
  timezone: string | null;
  skill_level: string | null;
  constraints_text: string | null;
  field_plan_text: string | null;
}

export interface RecommendationPhoto {
  status: "available" | "unavailable";
  source_record_id: string | null;
  species_name: string | null;
  display_url: string | null;
  source_url: string | null;
  creator: string | null;
  rights_holder: string | null;
  publisher: string | null;
  format: string | null;
  license_text: string | null;
  license_url: string | null;
  selection_reason: string | null;
  caveats: string[];
}

export interface RecommendationCall {
  status: "available" | "unavailable";
  source_record_id: string | null;
  recording_id: string | null;
  species_name: string | null;
  geographic_scope: "Arizona" | "Global example" | null;
  recording_type: string | null;
  quality: string | null;
  recordist: string | null;
  locality: string | null;
  country: string | null;
  source_url: string | null;
  audio_url: string | null;
  license_text: string | null;
  license_url: string | null;
  selection_reason: string | null;
  caveats: string[];
}

export interface Recommendation {
  recommendation_id: string;
  species_code: string | null;
  common_name: string | null;
  scientific_name: string | null;
  recommendation_group: "high_likelihood" | "uncommon_plausible" | string;
  rank_order: number;
  confidence_label: string | null;
  rationale_text: string | null;
  caveats: string[];
  photo: RecommendationPhoto;
  call: RecommendationCall;
}

export interface Evidence {
  evidence_id: string;
  recommendation_id: string | null;
  source: string;
  source_table: string | null;
  source_record_id: string | null;
  evidence_type: string;
  status: string;
  retrieved_at: string | null;
  summary: JsonObject;
  payload: JsonObject;
  caveats: string[];
}

export interface Media {
  evidence_id: string;
  recommendation_id: string | null;
  source_record_id: string | null;
  recording_id: string | null;
  status: string;
  species_name: string | null;
  recording_type: string | null;
  quality: string | null;
  recordist: string | null;
  license_text: string;
  license_url: string | null;
  source_url: string | null;
  audio_url: string | null;
  caveats: string[];
}

export interface ToolTrace {
  tool_trace_id: string;
  step_order: number;
  tool_name: string;
  tool_status: string;
  started_at: string | null;
  completed_at: string | null;
  input: JsonObject;
  output_summary: JsonObject;
  caveats: string[];
}

export interface TripPlanDetail {
  plan: TripPlan;
  recommendations: Recommendation[];
  evidence: Evidence[];
  weather: Evidence | null;
  media: Media[];
  tool_traces: ToolTrace[];
}

export interface LocationSuggestion {
  display_name: string;
  latitude: number;
  longitude: number;
  timezone: string;
  region_code: "US-AZ";
}

export interface BirdCatalogSummary {
  species_code: string;
  common_name: string | null;
  scientific_name: string | null;
  taxonomic_category: "species" | "hybrid";
  taxonomic_order: number;
  order_name: string | null;
  family_common_name: string | null;
  family_scientific_name: string | null;
  traits_status: "available" | "unavailable";
  recent_public_observation_count: number;
  latest_public_observation_at: string | null;
}

export interface BirdTaxonomy {
  family_code: string | null;
  report_as: string | null;
  extinct: boolean | null;
  extinct_year: number | null;
}

export interface BirdTraitSample {
  total_individuals: number | null;
  female_individuals: number | null;
  male_individuals: number | null;
  unknown_sex_individuals: number | null;
  complete_measures: number | null;
}

export interface BirdMorphology {
  beak_length_culmen_mm: number | null;
  beak_length_nares_mm: number | null;
  beak_width_mm: number | null;
  beak_depth_mm: number | null;
  tarsus_length_mm: number | null;
  wing_length_mm: number | null;
  kipps_distance_mm: number | null;
  secondary_length_mm: number | null;
  hand_wing_index: number | null;
  tail_length_mm: number | null;
  mass_g: number | null;
}

export interface BirdEcology {
  habitat: string | null;
  habitat_density_code: number | null;
  habitat_density_label: string | null;
  migration_code: number | null;
  migration_label: string | null;
  trophic_level: string | null;
  trophic_niche: string | null;
  primary_lifestyle: string | null;
}

export interface BirdTraitProvenance {
  dataset_doi: string | null;
  dataset_version: string | null;
  dataset_license: string | null;
  source_file_id: number | null;
  source_file_md5: string | null;
  loaded_at: string | null;
}

export interface BirdTraits {
  status: "available" | "unavailable";
  source_scientific_name: string | null;
  avonet_family: string | null;
  avonet_order_name: string | null;
  avibase_id: string | null;
  inference: boolean | null;
  traits_inferred: string | null;
  reference_species: string | null;
  mass_source: string | null;
  mass_reference_other: string | null;
  sample: BirdTraitSample;
  morphology: BirdMorphology;
  ecology: BirdEcology;
  provenance: BirdTraitProvenance;
}

export interface BirdPublicLocation {
  location_id: string;
  location_name: string | null;
  latitude: number;
  longitude: number;
  observation_count: number;
  latest_observation_at: string | null;
  notable_count: number;
}

export interface BirdProfile extends BirdCatalogSummary {
  region_code: "US-AZ";
  taxonomy: BirdTaxonomy;
  traits: BirdTraits;
  arizona_activity: {
    recent_public_observation_count: number;
    latest_public_observation_at: string | null;
    public_location_count: number;
    recent_public_notable_count: number;
    top_public_locations: BirdPublicLocation[];
  };
  gbif: { occurrence_count: number; latest_event_date: string | null };
  xeno_canto: {
    recording_count: number;
    latest_recording_date: string | null;
    representative_recording_id: string | null;
    representative_recordist: string | null;
    representative_recording_type: string | null;
    representative_recording_quality: string | null;
    representative_recording_license: string | null;
  };
  freshness: {
    species_list_loaded_at: string | null;
    taxonomy_loaded_at: string | null;
    ebird_observations_loaded_at: string | null;
    gbif_loaded_at: string | null;
    xeno_canto_loaded_at: string | null;
    catalog_freshness_at: string | null;
  };
}

export interface CreatePlanInput {
  location: string;
  location_selection?: LocationSuggestion;
  start_at: string;
  duration_minutes: number;
  skill_level?: string;
  constraints?: string;
}
