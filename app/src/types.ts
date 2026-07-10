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

export interface CreatePlanInput {
  location: string;
  location_selection?: LocationSuggestion;
  start_at: string;
  duration_minutes: number;
  skill_level?: string;
  constraints?: string;
}
