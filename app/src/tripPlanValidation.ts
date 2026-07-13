import { curatedPhotoKeys, validateAvailableCuratedPhoto } from "./curatedPhotoValidation";
import type {
  Evidence,
  LocationSuggestion,
  Media,
  PlanSummary,
  Recommendation,
  RecommendationCall,
  RecommendationPhoto,
  ToolTrace,
  TripCalendarInviteStatus,
  TripPlan,
  TripPlanDetail,
} from "./types";

type Row = Record<string, unknown>;
const IDENTIFIER = /^[A-Za-z0-9_-]{1,128}$/;
const TOKEN = /^[A-Za-z0-9_.:-]{1,128}$/;
const FORBIDDEN_JSON_KEY = /(?:^|[_-])(?:password|secret|api[_-]?key|private[_-]?key|access[_-]?token|refresh[_-]?token|raw[_-]?model(?:[_-]response)?)(?:$|[_-])/i;

function invalid(): never { throw new Error("Invalid trip planner response"); }
function exact(value: unknown, keys: readonly string[]): Row {
  if (typeof value !== "object" || value === null || Array.isArray(value)) invalid();
  const row = value as Row;
  const actual = Object.keys(row).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) invalid();
  return row;
}
function string(value: unknown, max: number, nullable = false, empty = false): value is string | null {
  return (nullable && value === null) || (typeof value === "string" && value.length <= max && (empty || value.length > 0));
}
function finite(value: unknown, min = -Number.MAX_VALUE, max = Number.MAX_VALUE): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}
function integer(value: unknown, min: number, max: number): value is number {
  return Number.isSafeInteger(value) && (value as number) >= min && (value as number) <= max;
}
const ISO_TIMESTAMP = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|([+-])(\d{2}):(\d{2}))?$/;
function timestampMicros(value: string): bigint | null {
  if (value.length > 64) return null;
  const match = ISO_TIMESTAMP.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  const offsetHour = match[10] ? Number(match[10]) : 0;
  const offsetMinute = match[11] ? Number(match[11]) : 0;
  if (year < 1 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59
    || offsetHour > 23 || offsetMinute > 59) return null;
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (day < 1 || day > days[month - 1]) return null;
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  date.setUTCHours(hour, minute, second, 0);
  let micros = BigInt(date.getTime()) * 1000n + BigInt((match[7] || "").padEnd(6, "0"));
  if (match[9]) {
    const offset = BigInt(offsetHour * 60 + offsetMinute) * 60_000_000n;
    micros += match[9] === "+" ? -offset : offset;
  }
  return micros;
}
function timestamp(value: unknown, nullable = false): value is string | null {
  return (nullable && value === null) || (typeof value === "string" && timestampMicros(value) !== null);
}
function strings(value: unknown, maxItems: number, maxLength = 500): value is string[] {
  return Array.isArray(value) && value.length <= maxItems
    && value.every((item) => typeof item === "string" && item.length > 0 && item.length <= maxLength);
}
function identifier(value: unknown, nullable = false): value is string | null {
  return (nullable && value === null) || (typeof value === "string" && IDENTIFIER.test(value));
}

function boundedJsonObject(value: unknown): Row {
  let nodes = 0;
  function visit(item: unknown, depth: number): void {
    nodes += 1;
    if (nodes > 600 || depth > 5) invalid();
    if (item === null || typeof item === "boolean") return;
    if (typeof item === "number") { if (!Number.isFinite(item)) invalid(); return; }
    if (typeof item === "string") { if (item.length > 4000) invalid(); return; }
    if (Array.isArray(item)) { if (item.length > 100) invalid(); item.forEach((child) => visit(child, depth + 1)); return; }
    if (typeof item !== "object") invalid();
    const entries = Object.entries(item as Row);
    if (entries.length > 60) invalid();
    for (const [key, child] of entries) {
      if (!/^[A-Za-z0-9_.:-]{1,100}$/.test(key) || FORBIDDEN_JSON_KEY.test(key)) invalid();
      visit(child, depth + 1);
    }
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) invalid();
  visit(value, 0);
  return value as Row;
}

function caveats(value: unknown): string[] {
  if (!strings(value, 30, 1000) || new Set(value).size !== value.length) invalid();
  return value;
}

function location(value: unknown): LocationSuggestion {
  const row = exact(value, [
    "display_name", "latitude", "longitude", "timezone", "region_code",
    "source", "source_id", "place_type",
  ]);
  if (!string(row.display_name, 300) || /[\u0000-\u001f\u007f]/.test(row.display_name as string)
    || !finite(row.latitude, 31, 38) || !finite(row.longitude, -115, -108)
    || row.timezone !== "America/Phoenix" || row.region_code !== "US-AZ"
    || (row.source !== "ebird_hotspot" && row.source !== "open_meteo")
    || !string(row.source_id, 64) || !/^[A-Za-z0-9_-]+$/.test(row.source_id as string)
    || (row.source === "open_meteo" && !(row.source_id as string).startsWith("open_meteo_"))
    || row.place_type !== (row.source === "ebird_hotspot" ? "Birding hotspot" : "Arizona place")) invalid();
  return row as unknown as LocationSuggestion;
}

export function validateLocationSearch(value: unknown): LocationSuggestion[] {
  const row = exact(value, ["locations"]);
  if (!Array.isArray(row.locations) || row.locations.length > 5) invalid();
  const locations = row.locations.map(location);
  const sourceIds = locations.map((item) => `${item.source}|${item.source_id}`);
  const normalized = (value: string) => value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("en").replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
  if (new Set(sourceIds).size !== sourceIds.length
    || locations.some((item, index) => locations.slice(0, index).some((prior) =>
      normalized(prior.display_name) === normalized(item.display_name)
      && Math.abs(prior.latitude - item.latitude) <= 0.001
      && Math.abs(prior.longitude - item.longitude) <= 0.001))) invalid();
  return locations;
}

function planSummary(value: unknown): PlanSummary {
  const row = exact(value, [
    "trip_plan_id", "requested_location", "normalized_location_name", "window_start", "window_end",
    "duration_minutes", "plan_status", "caveats", "created_at", "updated_at",
  ]);
  if (!identifier(row.trip_plan_id) || !string(row.requested_location, 300)
    || !string(row.normalized_location_name, 300, true) || !timestamp(row.window_start)
    || !timestamp(row.window_end) || !integer(row.duration_minutes, 1, 1440)
    || row.plan_status !== "complete" || !timestamp(row.created_at) || !timestamp(row.updated_at)) invalid();
  const start = timestampMicros(row.window_start as string)!;
  const end = timestampMicros(row.window_end as string)!;
  if (end - start !== BigInt(row.duration_minutes as number) * 60_000_000n
    || timestampMicros(row.created_at as string)! > timestampMicros(row.updated_at as string)!) invalid();
  return { ...(row as unknown as PlanSummary), caveats: caveats(row.caveats) };
}

export function validatePlanList(value: unknown): PlanSummary[] {
  const row = exact(value, ["plans"]);
  if (!Array.isArray(row.plans) || row.plans.length > 100) invalid();
  const plans = row.plans.map(planSummary);
  if (new Set(plans.map((plan) => plan.trip_plan_id)).size !== plans.length) invalid();
  return plans;
}

function plan(value: unknown): TripPlan {
  const row = exact(value, [
    "trip_plan_id", "requested_location", "normalized_location_name", "window_start", "window_end",
    "duration_minutes", "plan_status", "caveats", "created_at", "updated_at", "latitude", "longitude",
    "region_code", "timezone", "skill_level", "constraints_text", "field_plan_text",
  ]);
  const summary = planSummary(Object.fromEntries([
    "trip_plan_id", "requested_location", "normalized_location_name", "window_start", "window_end",
    "duration_minutes", "plan_status", "caveats", "created_at", "updated_at",
  ].map((key) => [key, row[key]])));
  if ((row.latitude !== null && !finite(row.latitude, -90, 90))
    || (row.longitude !== null && !finite(row.longitude, -180, 180))
    || !string(row.region_code, 32, true) || !string(row.timezone, 64, true)
    || (row.skill_level !== null && !["beginner", "intermediate", "advanced"].includes(String(row.skill_level)))
    || !string(row.constraints_text, 1000, true, true) || !string(row.field_plan_text, 20000, true, true)) invalid();
  if ((row.latitude === null) !== (row.longitude === null)
    || (row.region_code === "US-AZ" && row.timezone !== "America/Phoenix")) invalid();
  return { ...summary, ...(row as unknown as TripPlan), caveats: summary.caveats };
}

const photoKeys = [...curatedPhotoKeys];
function photo(value: unknown): RecommendationPhoto {
  const row = exact(value, photoKeys);
  if (row.status !== "available" && row.status !== "unavailable") invalid();
  for (const [key, max] of Object.entries({ source_record_id: 500, species_name: 300, display_url: 2048, source_url: 2048, creator: 500, rights_holder: 500, publisher: 500, format: 128, license_text: 500, license_url: 2048, selection_reason: 1000, license_code: 500 })) {
    if (!string(row[key], max, true, true)) invalid();
  }
  if (row.provider !== null && row.provider !== "inaturalist") invalid();
  if (!(row.original_width === null || integer(row.original_width, 1, 100000))
    || !(row.original_height === null || integer(row.original_height, 1, 100000))) invalid();
  return { ...(row as unknown as RecommendationPhoto), caveats: caveats(row.caveats) };
}
const callKeys = ["status", "source_record_id", "recording_id", "species_name", "geographic_scope", "recording_type", "quality", "recordist", "locality", "country", "source_url", "audio_url", "license_text", "license_url", "selection_reason", "caveats"];
function call(value: unknown): RecommendationCall {
  const row = exact(value, callKeys);
  if ((row.status !== "available" && row.status !== "unavailable")
    || (row.geographic_scope !== null && row.geographic_scope !== "Arizona" && row.geographic_scope !== "Global example")) invalid();
  for (const [key, max] of Object.entries({ source_record_id: 128, recording_id: 128, species_name: 300, recording_type: 300, quality: 64, recordist: 500, locality: 500, country: 200, source_url: 2048, audio_url: 2048, license_text: 500, license_url: 2048, selection_reason: 1000 })) {
    if (!string(row[key], max, true, true)) invalid();
  }
  return { ...(row as unknown as RecommendationCall), caveats: caveats(row.caveats) };
}

function recommendation(value: unknown): Recommendation {
  const row = exact(value, ["recommendation_id", "species_code", "common_name", "scientific_name", "recommendation_group", "rank_order", "confidence_label", "rationale_text", "caveats", "photo", "call"]);
  if (!identifier(row.recommendation_id) || !string(row.species_code, 64, true)
    || !string(row.common_name, 300, true) || !string(row.scientific_name, 300, true)
    || (row.recommendation_group !== "high_likelihood" && row.recommendation_group !== "uncommon_plausible")
    || !integer(row.rank_order, 1, 10000) || !string(row.confidence_label, 200, true)
    || !string(row.rationale_text, 4000, true, true)) invalid();
  return { ...(row as unknown as Recommendation), caveats: caveats(row.caveats), photo: photo(row.photo), call: call(row.call) };
}

function evidence(value: unknown): Evidence {
  const row = exact(value, ["evidence_id", "recommendation_id", "source", "source_table", "source_record_id", "evidence_type", "status", "retrieved_at", "summary", "payload", "caveats"]);
  if (!identifier(row.evidence_id) || !identifier(row.recommendation_id, true)
    || !string(row.source, 128) || !string(row.source_table, 256, true, true)
    || !string(row.source_record_id, 500, true, true) || !string(row.evidence_type, 128)
    || !string(row.status, 64) || !timestamp(row.retrieved_at, true)) invalid();
  return { ...(row as unknown as Evidence), summary: boundedJsonObject(row.summary), payload: boundedJsonObject(row.payload), caveats: caveats(row.caveats) };
}

function media(value: unknown): Media {
  const row = exact(value, ["evidence_id", "recommendation_id", "source_record_id", "recording_id", "status", "species_name", "recording_type", "quality", "recordist", "license_text", "license_url", "source_url", "audio_url", "caveats"]);
  if (!identifier(row.evidence_id) || !identifier(row.recommendation_id, true) || !string(row.status, 64)
    || !string(row.license_text, 500, false, true)) invalid();
  for (const [key, max] of Object.entries({ source_record_id: 128, recording_id: 128, species_name: 300, recording_type: 300, quality: 64, recordist: 500, license_url: 2048, source_url: 2048, audio_url: 2048 })) {
    if (!string(row[key], max, true, true)) invalid();
  }
  return { ...(row as unknown as Media), caveats: caveats(row.caveats) };
}

function trace(value: unknown): ToolTrace {
  const row = exact(value, ["tool_trace_id", "step_order", "tool_name", "tool_status", "started_at", "completed_at", "input", "output_summary", "caveats"]);
  if (!identifier(row.tool_trace_id) || !integer(row.step_order, 1, 1000)
    || !string(row.tool_name, 128) || !string(row.tool_status, 64)
    || !timestamp(row.started_at, true) || !timestamp(row.completed_at, true)) invalid();
  if (row.started_at !== null && row.completed_at !== null
    && timestampMicros(row.started_at as string)! > timestampMicros(row.completed_at as string)!) invalid();
  return { ...(row as unknown as ToolTrace), input: boundedJsonObject(row.input), output_summary: boundedJsonObject(row.output_summary), caveats: caveats(row.caveats) };
}

function unique(values: string[]): boolean { return new Set(values).size === values.length; }
function equivalent(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length
      && left.every((item, index) => equivalent(item, right[index]));
  }
  if (typeof left !== "object" || left === null || typeof right !== "object" || right === null) return false;
  const leftRow = left as Row;
  const rightRow = right as Row;
  const keys = Object.keys(leftRow).sort();
  return keys.length === Object.keys(rightRow).length
    && keys.every((key) => Object.hasOwn(rightRow, key) && equivalent(leftRow[key], rightRow[key]));
}
function allNull(row: RecommendationPhoto | RecommendationCall, keys: readonly string[]): boolean {
  return keys.every((key) => (row as unknown as Row)[key] === null);
}
function recordingIdFromEvidence(item: Evidence): string | null {
  const values = [item.source_record_id, item.summary.source_record_id, item.summary.recording_id,
    item.payload.source_record_id, item.payload.recording_id];
  let found = false;
  const normalized = new Set<string>();
  for (const value of values) {
    if (value === null || value === undefined) continue;
    found = true;
    if (typeof value !== "string") return null;
    const match = /^(?:XC)?(\d+)$/.exec(value);
    if (!match) return null;
    normalized.add(match[1].replace(/^0+(?=\d)/, ""));
  }
  return found && normalized.size === 1 ? [...normalized][0] : null;
}
function exactSpecies(recommendation: Recommendation, speciesName: string | null): boolean {
  return recommendation.scientific_name !== null && speciesName !== null
    && recommendation.scientific_name.toLocaleLowerCase() === speciesName.toLocaleLowerCase();
}
export function validateCalendarInviteStatus(value: unknown): TripCalendarInviteStatus {
  const row = exact(value, ["status", "sequence", "outbox_id", "allowed_actions", "can_retry", "updated_at", "acceptance_notice"]);
  const statuses = ["not_created", "pending", "claimed", "retry_wait", "accepted", "failed", "delivery_unknown", "superseded"] as const;
  const actions = ["send", "send_update", "retry_failed", "mark_delivered", "mark_not_delivered_and_retry"] as const;
  if (!statuses.includes(row.status as typeof statuses[number])
    || !(row.sequence === null || integer(row.sequence, 0, Number.MAX_SAFE_INTEGER))
    || !(row.outbox_id === null || (string(row.outbox_id, 128) && /^trip_outbox_[0-9a-f]{64}$/.test(row.outbox_id)))
    || !Array.isArray(row.allowed_actions) || row.allowed_actions.length > 2
    || row.allowed_actions.some((item) => !actions.includes(item as typeof actions[number]))
    || typeof row.can_retry !== "boolean"
    || !(row.updated_at === null || (string(row.updated_at, 64) && timestampMicros(row.updated_at) !== null))
    || !(row.acceptance_notice === null || row.acceptance_notice === "Accepted by local mail bridge")) invalid();
  const status = row.status as typeof statuses[number];
  const expectedActions: Record<typeof statuses[number], string[]> = {
    not_created: ["send"], pending: [], claimed: [], retry_wait: [],
    accepted: ["send_update"], failed: ["retry_failed"],
    delivery_unknown: ["mark_delivered", "mark_not_delivered_and_retry"], superseded: [],
  };
  if (JSON.stringify(row.allowed_actions) !== JSON.stringify(expectedActions[status])
    || row.can_retry !== (status === "failed")
    || (status === "not_created"
      ? row.sequence !== null || row.outbox_id !== null || row.updated_at !== null
      : row.sequence === null || row.outbox_id === null || row.updated_at === null)
    || (status === "accepted") !== (row.acceptance_notice === "Accepted by local mail bridge")) invalid();
  return row as unknown as TripCalendarInviteStatus;
}

export function validatePlanDetail(value: unknown): TripPlanDetail {
  const row = exact(value, ["plan", "recommendations", "evidence", "weather", "media", "tool_traces", "calendar_invite"]);
  if (!Array.isArray(row.recommendations) || row.recommendations.length > 20
    || !Array.isArray(row.evidence) || row.evidence.length > 1000
    || !Array.isArray(row.media) || row.media.length > 100
    || !Array.isArray(row.tool_traces) || row.tool_traces.length > 50) invalid();
  const validatedPlan = plan(row.plan);
  const recommendations = row.recommendations.map(recommendation);
  const evidenceRows = row.evidence.map(evidence);
  const mediaRows = row.media.map(media);
  const traces = row.tool_traces.map(trace);
  const weather = row.weather === null ? null : evidence(row.weather);
  const recommendationIds = recommendations.map((item) => item.recommendation_id);
  if (!unique(recommendationIds) || !unique(evidenceRows.map((item) => item.evidence_id))
    || !unique(mediaRows.map((item) => item.evidence_id)) || !unique(traces.map((item) => item.tool_trace_id))
    || !unique(traces.map((item) => String(item.step_order)))) invalid();
  const recommendationSet = new Set(recommendationIds);
  if (evidenceRows.some((item) => item.recommendation_id !== null && !recommendationSet.has(item.recommendation_id))
    || mediaRows.some((item) => item.recommendation_id !== null && !recommendationSet.has(item.recommendation_id))) invalid();

  const weatherEvidence = evidenceRows.filter((item) => item.source === "open_meteo");
  if (weather === null ? weatherEvidence.length !== 0 : weatherEvidence.length !== 1
    || (weather !== null && (weather.recommendation_id !== null || weather.evidence_type !== "weather_elevation_context"
      || !equivalent(weather, weatherEvidence[0])))) invalid();

  const mediaEvidence = evidenceRows.filter((item) => item.source === "xeno_canto" && item.status === "available");
  if (mediaRows.length !== mediaEvidence.length
    || !unique(mediaEvidence.map((item) => item.evidence_id))) invalid();
  const mediaByEvidence = new Map(mediaRows.map((item) => [item.evidence_id, item]));
  for (const item of mediaEvidence) {
    const linked = mediaByEvidence.get(item.evidence_id);
    if (!linked || linked.recommendation_id !== item.recommendation_id
      || linked.source_record_id !== item.source_record_id
      || linked.recording_id !== recordingIdFromEvidence(item)) invalid();
  }

  const enrichmentByRecommendation = new Map<string, Evidence>();
  for (const item of evidenceRows.filter((row) => row.evidence_type === "recommendation_photo" || row.evidence_type === "recommendation_call")) {
    if (item.recommendation_id === null
      || (item.evidence_type === "recommendation_photo"
        ? item.source !== "inaturalist" && item.source !== "curated_photo"
        : item.source !== "xeno_canto")) invalid();
    const key = `${item.recommendation_id}|${item.evidence_type}`;
    if (enrichmentByRecommendation.has(key)) invalid();
    enrichmentByRecommendation.set(key, item);
  }
  for (const item of recommendations) {
    const linkedPhoto = enrichmentByRecommendation.get(`${item.recommendation_id}|recommendation_photo`);
    const linkedCall = enrichmentByRecommendation.get(`${item.recommendation_id}|recommendation_call`);
    if (item.photo.status === "unavailable") {
      if (!allNull(item.photo, photoKeys.filter((key) => key !== "status" && key !== "caveats"))) invalid();
    } else if (!linkedPhoto || linkedPhoto.status !== "available"
      || item.photo.source_record_id !== linkedPhoto.source_record_id
      || linkedPhoto.source !== item.photo.provider
      || !validateAvailableCuratedPhoto(item.photo as unknown as Row, item.scientific_name)
      || !equivalent(item.photo.caveats, linkedPhoto.caveats)) invalid();
    if (item.call.status === "unavailable") {
      if (!allNull(item.call, callKeys.filter((key) => key !== "status" && key !== "caveats"))) invalid();
    } else if (!linkedCall || linkedCall.status !== "available"
      || item.call.source_record_id !== linkedCall.source_record_id
      || item.call.recording_id !== recordingIdFromEvidence(linkedCall)
      || !exactSpecies(item, item.call.species_name)
      || item.call.geographic_scope === null || item.call.recordist === null
      || item.call.source_url === null || item.call.audio_url === null
      || item.call.license_text === null || item.call.license_url === null
      || !equivalent(item.call.caveats, linkedCall.caveats)) invalid();
  }

  for (const group of ["high_likelihood", "uncommon_plausible"]) {
    const ranks = recommendations.filter((item) => item.recommendation_group === group).map((item) => item.rank_order);
    if (!unique(ranks.map(String))) invalid();
  }
  return { plan: validatedPlan, recommendations, evidence: evidenceRows, weather, media: mediaRows, tool_traces: traces, calendar_invite: validateCalendarInviteStatus(row.calendar_invite) };
}
