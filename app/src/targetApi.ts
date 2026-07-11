import type { CreateTargetPlanInput, TargetPlan } from "./types";

type Row = Record<string, unknown>;

function exact(value: unknown, keys: string[]): Row {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid target plan response");
  const row = value as Row;
  if (Object.keys(row).sort().join("|") !== [...keys].sort().join("|")) throw new Error("Invalid target plan response");
  return row;
}
function text(value: unknown, max: number, nullable = false): value is string | null {
  return (nullable && value === null) || (typeof value === "string" && value.length > 0 && value.length <= max);
}
function number(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}
function timestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value));
}
function strings(value: unknown, max: number): value is string[] {
  return Array.isArray(value) && value.length <= max && value.every((item) => typeof item === "string" && item.length > 0 && item.length <= 500);
}
function nullableFinite(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}
const actionIds = new Set(["try_top_location", "arrive_early", "review_freshness", "check_weather", "verify_access"]);

function validate(value: unknown): TargetPlan {
  const keys = ["target_plan_id","species_code","common_name","scientific_name","taxonomic_category","origin","radius_miles","radius_km","window_start","window_end","duration_minutes","candidates","weather","action_ids","guidance","caveats","evidence_freshness_at","created_at"];
  const row = exact(value, keys);
  if (typeof row.target_plan_id !== "string" || !/^target_[0-9a-f]{32}$/.test(row.target_plan_id)
    || typeof row.species_code !== "string" || !/^[A-Za-z0-9]{1,64}$/.test(row.species_code)
    || !text(row.common_name, 200, true) || !text(row.scientific_name, 200, true)
    || (row.taxonomic_category !== "species" && row.taxonomic_category !== "hybrid")
    || !number(row.radius_miles, 1, 300) || !number(row.radius_km, 1.609, 483)
    || !timestamp(row.window_start) || !timestamp(row.window_end)
    || !Number.isSafeInteger(row.duration_minutes) || !number(row.duration_minutes, 1, 1440)
    || !strings(row.action_ids, 5) || row.action_ids.length === 0
    || row.action_ids.some((item) => !actionIds.has(item))
    || new Set(row.action_ids).size !== row.action_ids.length
    || !strings(row.guidance, 5) || row.guidance.length !== row.action_ids.length
    || !strings(row.caveats, 20)
    || (row.evidence_freshness_at !== null && !timestamp(row.evidence_freshness_at))
    || !timestamp(row.created_at)) throw new Error("Invalid target plan response");
  const origin = exact(row.origin, ["requested_location","normalized_location_name","latitude","longitude","timezone","region_code"]);
  if (!text(origin.requested_location,300) || !text(origin.normalized_location_name,300)
    || !number(origin.latitude,-90,90) || !number(origin.longitude,-180,180)
    || !text(origin.timezone,64) || origin.region_code !== "US-AZ") throw new Error("Invalid target plan response");
  if (!Array.isArray(row.candidates) || row.candidates.length > 10) throw new Error("Invalid target plan response");
  for (const item of row.candidates) {
    const candidate = exact(item,["location_id","location_name","latitude","longitude","observation_count","latest_observation_at","distance_km","distance_miles","evidence_loaded_at"]);
    if (!text(candidate.location_id,128) || !text(candidate.location_name,300,true)
      || !number(candidate.latitude,-90,90) || !number(candidate.longitude,-180,180)
      || !Number.isSafeInteger(candidate.observation_count) || (candidate.observation_count as number) < 1
      || !timestamp(candidate.latest_observation_at) || !number(candidate.distance_km,0,483)
      || !number(candidate.distance_miles,0,300)
      || (candidate.evidence_loaded_at !== null && !timestamp(candidate.evidence_loaded_at))
      || (candidate.distance_miles as number) > (row.radius_miles as number) + 0.001
      || Math.abs((candidate.distance_km as number) - (candidate.distance_miles as number) * 1.609344) > 0.02) throw new Error("Invalid target plan response");
  }
  const weather = exact(row.weather,["status","retrieved_at","forecast_summary","units","elevation_m","caveats"]);
  const summary = exact(weather.forecast_summary, [
    "temperature_2m_min","temperature_2m_max","temperature_2m_avg","relative_humidity_2m_avg",
    "precipitation_probability_max","precipitation_sum","wind_speed_10m_max","wind_gusts_10m_max","weather_codes",
  ]);
  const units = exact(weather.units, ["temperature","relative_humidity","precipitation_probability","precipitation","wind_speed","wind_gusts","elevation"]);
  const numericSummaryKeys = Object.keys(summary).filter((key) => key !== "weather_codes");
  if (!(["available","partial","unavailable"] as unknown[]).includes(weather.status)
    || !timestamp(weather.retrieved_at)
    || numericSummaryKeys.some((key) => !nullableFinite(summary[key]))
    || !Array.isArray(summary.weather_codes) || summary.weather_codes.length > 100
    || summary.weather_codes.some((item) => !Number.isSafeInteger(item))
    || Object.values(units).some((item) => typeof item !== "string" || item.length === 0 || item.length > 32)
    || !nullableFinite(weather.elevation_m) || (weather.elevation_m !== null && !number(weather.elevation_m,-500,10000))
    || !strings(weather.caveats,10)) throw new Error("Invalid target plan response");
  const hasForecast = numericSummaryKeys.some((key) => summary[key] !== null) || summary.weather_codes.length > 0;
  if ((weather.status === "available" && (!hasForecast || weather.elevation_m === null))
    || (weather.status === "partial" && !hasForecast && weather.elevation_m === null)
    || (weather.status === "unavailable" && (hasForecast || weather.elevation_m !== null))) throw new Error("Invalid target plan response");
  const windowMilliseconds = Date.parse(row.window_end as string) - Date.parse(row.window_start as string);
  const expectedFreshness = (row.candidates as TargetPlan["candidates"])
    .map((candidate) => candidate.evidence_loaded_at).filter((item): item is string => item !== null).sort().at(-1) ?? null;
  if (windowMilliseconds !== (row.duration_minutes as number) * 60_000
    || Math.abs((row.radius_km as number) - (row.radius_miles as number) * 1.609344) > 0.01
    || (!row.candidates.length && (row.action_ids as string[]).some((action) => action === "try_top_location" || action === "verify_access"))
    || row.evidence_freshness_at !== expectedFreshness) throw new Error("Invalid target plan response");
  return row as unknown as TargetPlan;
}

const safeErrors: Record<string, string> = {
  "400:invalid_location": "Choose a location inside Arizona.",
  "400:invalid_request": "Check the target-planning inputs and try again.",
  "404:not_found": "Target plan not found.",
  "409:planner_busy": "Another target plan is being created. Try again shortly.",
  "422:invalid_request": "Check the target-planning inputs and try again.",
  "429:model_rate_limited": "The configured model is rate limited. Try again later.",
  "500:planner_failed": "The target planner could not complete the plan.",
  "503:database_unavailable": "The local target plans are unavailable.",
  "503:model_authentication_failed": "The configured model is unavailable.",
  "503:model_not_configured": "The configured model is unavailable.",
  "503:model_unavailable": "The configured model is unavailable.",
  "504:model_timeout": "The configured model timed out. Try again.",
};
async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, { ...init, headers: { "Content-Type": "application/json" } });
  let body: unknown;
  try { body = await response.json(); } catch { throw new Error("The target planner is unavailable"); }
  if (!response.ok) {
    let code: string | null = null;
    try {
      const envelope = exact(body, ["error"]);
      const error = exact(envelope.error, ["code", "message"]);
      if (typeof error.code === "string" && typeof error.message === "string") code = error.code;
    } catch { /* malformed errors use the fixed generic message */ }
    throw new Error(code ? safeErrors[`${response.status}:${code}`] || "The target planner is unavailable" : "The target planner is unavailable");
  }
  return body;
}

export async function createTargetPlan(input: CreateTargetPlanInput): Promise<TargetPlan> {
  return validate(await request("/api/target-plans", { method: "POST", body: JSON.stringify(input) }));
}
export async function getTargetPlan(id: string): Promise<TargetPlan> {
  if (!/^target_[0-9a-f]{32}$/.test(id)) throw new Error("Invalid target plan identifier");
  return validate(await request(`/api/target-plans/${id}`));
}
