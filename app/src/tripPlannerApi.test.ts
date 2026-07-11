import { afterEach, describe, expect, it, vi } from "vitest";
import { getPlan, listPlans, searchLocations } from "./api";

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
