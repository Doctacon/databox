import type {
  CreatePlanInput,
  LocationSuggestion,
  PlanSummary,
  TripCalendarInviteStatus,
  TripPlanDetail,
} from "./types";
import { validateCalendarInviteStatus, validateLocationSearch, validatePlanDetail, validatePlanList } from "./tripPlanValidation";

type Row = Record<string, unknown>;
const GENERIC_ERROR = "The local service could not complete the request";
const safeErrors: Record<string, string> = {
  "400:invalid_location": "Choose a location inside Arizona. Arizona coordinates require a negative longitude.",
  "400:invalid_request": "Check the trip-planning inputs and try again.",
  "404:not_found": "Trip plan not found.",
  "409:planner_busy": "Another trip plan is being created. Try again shortly.",
  "422:invalid_request": "Check the trip-planning inputs and try again.",
  "429:model_rate_limited": "The configured model is rate limited. Try again later.",
  "500:planner_failed": "The trip planner could not complete the plan.",
  "503:database_busy": "The warehouse is refreshing. Try again shortly.",
  "503:database_unavailable": "The local warehouse is unavailable.",
  "503:geocoder_unavailable": "Location search is unavailable; enter Arizona coordinates.",
  "503:model_authentication_failed": "The configured model is unavailable.",
  "503:model_not_configured": "The configured model is unavailable.",
  "503:model_unavailable": "The configured model is unavailable.",
  "504:model_timeout": "The configured model timed out. Try again.",
  "409:confirmation_required": "Confirm the calendar invitation action.",
  "409:delivery_busy": "Another calendar operation is in progress. Try again shortly.",
  "409:invalid_plan": "This trip plan is incomplete or changed and cannot be sent.",
  "409:invalid_state": "The calendar invitation state changed. Reload the plan and try again.",
  "503:smtp_not_configured": "Configure the local mail bridge before sending a calendar invitation.",
};

function exactError(value: unknown): string | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const envelope = value as Row;
  if (Object.keys(envelope).length !== 1 || !("error" in envelope)
    || typeof envelope.error !== "object" || envelope.error === null || Array.isArray(envelope.error)) return null;
  const error = envelope.error as Row;
  if (Object.keys(error).sort().join("|") !== "code|message" || typeof error.code !== "string" || typeof error.message !== "string") return null;
  return error.code;
}

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  let body: unknown;
  try { body = await response.json(); }
  catch { throw new Error(GENERIC_ERROR); }
  if (!response.ok) {
    const code = exactError(body);
    throw new Error(code ? safeErrors[`${response.status}:${code}`] || GENERIC_ERROR : GENERIC_ERROR);
  }
  return body;
}

export async function searchLocations(
  query: string,
  signal?: AbortSignal,
): Promise<LocationSuggestion[]> {
  return validateLocationSearch(await request(
    `/api/locations?q=${encodeURIComponent(query)}`,
    { signal },
  ));
}

export async function listPlans(): Promise<PlanSummary[]> {
  return validatePlanList(await request("/api/trip-plans"));
}

export async function getPlan(id: string): Promise<TripPlanDetail> {
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(id)) throw new Error("Invalid trip plan identifier");
  const detail = validatePlanDetail(await request(`/api/trip-plans/${encodeURIComponent(id)}`));
  if (detail.plan.trip_plan_id !== id) throw new Error("Invalid trip planner response");
  return detail;
}

export async function createPlan(input: CreatePlanInput): Promise<TripPlanDetail> {
  return validatePlanDetail(await request("/api/trip-plans", {
    method: "POST",
    body: JSON.stringify(input),
  }));
}

export type TripCalendarAction = TripCalendarInviteStatus["allowed_actions"][number];

function validateCalendarActionResponse(value: unknown): TripCalendarInviteStatus {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Invalid calendar invitation response");
  const row = value as Row;
  if (Object.keys(row).sort().join("|") !== "delivery|outbox_id"
    || typeof row.outbox_id !== "string" || !/^trip_outbox_[0-9a-f]{64}$/.test(row.outbox_id)) {
    throw new Error("Invalid calendar invitation response");
  }
  let delivery: TripCalendarInviteStatus;
  try { delivery = validateCalendarInviteStatus(row.delivery); }
  catch { throw new Error("Invalid calendar invitation response"); }
  if (delivery.outbox_id !== row.outbox_id) throw new Error("Invalid calendar invitation response");
  return delivery;
}

export async function actOnTripCalendarInvite(
  planId: string,
  current: TripCalendarInviteStatus,
  action: TripCalendarAction,
): Promise<TripCalendarInviteStatus> {
  let validated: TripCalendarInviteStatus;
  try { validated = validateCalendarInviteStatus(current); }
  catch { throw new Error("Invalid calendar invitation action"); }
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(planId) || !validated.allowed_actions.includes(action)) {
    throw new Error("Invalid calendar invitation action");
  }
  const path = action === "send" || action === "send_update"
    ? `/api/trip-plans/${encodeURIComponent(planId)}/calendar-invite?confirm=true`
    : `/api/trip-calendar-deliveries/${encodeURIComponent(validated.outbox_id!)}/${action === "retry_failed" ? "retry" : action === "mark_delivered" ? "mark-delivered" : "mark-not-delivered-and-retry"}?confirm=true`;
  return validateCalendarActionResponse(await request(path, { method: "POST" }));
}
