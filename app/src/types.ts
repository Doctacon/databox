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
  skill_level: string | null;
  constraints_text: string | null;
  field_plan_text: string | null;
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
  media: Evidence[];
  tool_traces: ToolTrace[];
}

export interface CreatePlanInput {
  location: string;
  start_at: string;
  duration_minutes: number;
  skill_level?: string;
  constraints?: string;
}
