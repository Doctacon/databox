import { afterEach, describe, expect, it, vi } from "vitest";
import { createTargetPlan, getTargetPlan } from "./targetApi";
import { targetPlan } from "./targetTestData";
function response(body: unknown, ok = true) { return Promise.resolve({ ok, json: () => Promise.resolve(body) } as Response); }
afterEach(() => vi.restoreAllMocks());

describe("target API boundary", () => {
  it("validates a complete persisted plan and exact request identity", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(() => response(targetPlan));
    expect(await getTargetPlan(targetPlan.target_plan_id)).toEqual(targetPlan);
    expect(fetch).toHaveBeenCalledWith(`/api/target-plans/${targetPlan.target_plan_id}`, expect.anything());
  });
  it("rejects extra, private, malformed, and inconsistent fields", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ ...targetPlan, private_location: "secret" }));
    await expect(getTargetPlan(targetPlan.target_plan_id)).rejects.toThrow("Invalid target plan response");
  });
  it.each([
    { ...targetPlan, weather: { ...targetPlan.weather, forecast_summary: { ...targetPlan.weather.forecast_summary, arbitrary: 1 } } },
    { ...targetPlan, weather: { ...targetPlan.weather, forecast_summary: { ...targetPlan.weather.forecast_summary, temperature_2m_avg: Number.NaN } } },
    { ...targetPlan, weather: { ...targetPlan.weather, units: { ...targetPlan.weather.units, wind_speed: "" } } },
    { ...targetPlan, weather: { ...targetPlan.weather, status: "unavailable" } },
    { ...targetPlan, window_end: "2026-07-11T09:00:00" },
    { ...targetPlan, radius_km: 42 },
    { ...targetPlan, evidence_freshness_at: null },
    { ...targetPlan, candidates: [], evidence_freshness_at: null },
  ])("rejects malformed weather and internal relationships", async (invalid) => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(invalid));
    await expect(getTargetPlan(targetPlan.target_plan_id)).rejects.toThrow("Invalid target plan response");
    vi.restoreAllMocks();
  });
  it("posts the exact selected origin without credentials", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(() => response(targetPlan));
    await createTargetPlan({ species_code: "target1", location: "Prescott", location_selection: { display_name: "Prescott, AZ", latitude: 34, longitude: -112, timezone: "America/Phoenix", region_code: "US-AZ" }, radius_miles: 25, start_at: "2026-07-11T06:00:00", duration_minutes: 120 });
    const init = fetch.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(String(init.body)).not.toMatch(/cloudflare|password|api.?key/i);
  });
  it("suppresses malformed structured errors", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ error: { code: "failed", message: "raw", internal: "secret" } }, false));
    await expect(getTargetPlan(targetPlan.target_plan_id)).rejects.toThrow("The target planner is unavailable");
  });
  it("suppresses malformed non-json errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, json: () => Promise.reject(new Error("raw")) } as Response);
    await expect(getTargetPlan(targetPlan.target_plan_id)).rejects.toThrow("The target planner is unavailable");
  });
});
