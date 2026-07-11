import { afterEach, describe, expect, it, vi } from "vitest";
import { actOnTripCalendarInvite, getPlan, listPlans, searchLocations } from "./api";
import type { TripCalendarInviteStatus } from "./types";

function response(body: unknown, status: number) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}
afterEach(() => vi.restoreAllMocks());

const sparseDetail = {
  plan: {
    trip_plan_id: "expected", requested_location: "Prescott", normalized_location_name: "Prescott, Arizona",
    window_start: "2026-07-10T06:00:00", window_end: "2026-07-10T07:30:00", duration_minutes: 90,
    plan_status: "complete", caveats: [], created_at: "2026-07-09T12:00:00", updated_at: "2026-07-09T12:00:00",
    latitude: 34.54, longitude: -112.47, region_code: "US-AZ", timezone: "America/Phoenix",
    skill_level: null, constraints_text: null, field_plan_text: null,
  },
  recommendations: [], evidence: [], weather: null, media: [], tool_traces: [],
  calendar_invite: { status: "not_created", sequence: null, outbox_id: null, allowed_actions: ["send"], can_retry: false, updated_at: null, acceptance_notice: null },
};

describe("Trip Planner safe browser errors", () => {
  it.each([
    [503, "database_busy", "The warehouse is refreshing. Try again shortly."],
    [503, "geocoder_unavailable", "Location search is unavailable; enter Arizona coordinates."],
    [429, "model_rate_limited", "The configured model is rate limited. Try again later."],
  ])("maps %i/%s to a fixed safe message", async (status, code, expected) => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ error: { code, message: "/private/local.duckdb raw-model secret" } }, status));
    const action = code === "geocoder_unavailable" ? searchLocations("Prescott") : listPlans();
    await expect(action).rejects.toThrow(expected);
    await expect(action).rejects.not.toThrow(/private|raw-model|secret/);
  });

  it("requires a GET detail response to match the requested plan identity", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({
      ...sparseDetail, plan: { ...sparseDetail.plan, trip_plan_id: "different" },
    }, 200));
    await expect(getPlan("expected")).rejects.toThrow("Invalid trip planner response");

    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response(sparseDetail, 200));
    await expect(getPlan("expected")).resolves.toEqual(sparseDetail);
  });

  it("validates calendar actions and response relationships without exposing transport errors", async () => {
    const notCreated = sparseDetail.calendar_invite as TripCalendarInviteStatus;
    const accepted = {
      status: "accepted" as const, sequence: 0, outbox_id: `trip_outbox_${"a".repeat(64)}`,
      allowed_actions: ["send_update" as const], can_retry: false, updated_at: "2026-07-10T12:00:00Z",
      acceptance_notice: "Accepted by local mail bridge" as const,
    };
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({ outbox_id: accepted.outbox_id, delivery: accepted }, 200));
    await expect(actOnTripCalendarInvite("expected", notCreated, "send")).resolves.toEqual(accepted);
    expect(fetch).toHaveBeenCalledWith("/api/trip-plans/expected/calendar-invite?confirm=true", expect.objectContaining({ method: "POST" }));

    fetch.mockImplementationOnce(() => response({ outbox_id: `trip_outbox_${"b".repeat(64)}`, delivery: accepted }, 200));
    await expect(actOnTripCalendarInvite("expected", accepted, "send_update")).rejects.toThrow("Invalid calendar invitation response");

    fetch.mockImplementationOnce(() => response({ error: { code: "invalid_state", message: "recipient@example.test /private/smtp payload" } }, 409));
    const rejected = actOnTripCalendarInvite("expected", accepted, "send_update");
    await expect(rejected).rejects.toThrow("The calendar invitation state changed. Reload the plan and try again.");
    await expect(rejected).rejects.not.toThrow(/recipient|private|smtp|payload/);
  });

  it("rejects actions not explicitly allowed by the current validated state without transport", async () => {
    const fetch = vi.spyOn(globalThis, "fetch");
    await expect(actOnTripCalendarInvite("expected", sparseDetail.calendar_invite as TripCalendarInviteStatus, "retry_failed")).rejects.toThrow("Invalid calendar invitation action");
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    { error: { code: "unknown_code", message: "/private/path secret" } },
    { error: { code: "database_busy", message: "raw", internal: "secret" } },
    { message: "raw-model response" },
  ])("uses a generic message for unknown or malformed errors", async (body) => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(body, 503));
    await expect(listPlans()).rejects.toThrow("The local service could not complete the request");
    await expect(listPlans()).rejects.not.toThrow(/private|raw-model|secret/);
  });
});
