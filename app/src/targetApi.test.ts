import { afterEach, describe, expect, it, vi } from "vitest";
import { createTargetPlan, getTargetPlan } from "./targetApi";
import { targetPlan } from "./targetTestData";
import type { TargetPlan } from "./types";
function response(body: unknown, ok = true, status = ok ? 200 : 503) { return Promise.resolve({ ok, status, json: () => Promise.resolve(body) } as Response); }
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
  it("rejects impossible or non-ISO timestamps in every target timestamp family", async () => {
    const mutations: ((value: TargetPlan) => void)[] = [
      (value) => { value.window_start = "2026-02-29T06:00:00"; },
      (value) => { value.window_end = "2026-01-01T06:00:00+24:00"; },
      (value) => { value.evidence_freshness_at = "0"; },
      (value) => { value.created_at = "2026-04-31T06:00:00Z"; },
      (value) => { value.candidates[0].latest_observation_at = "2026-01-01T24:00:00"; },
      (value) => { value.candidates[0].evidence_loaded_at = 0 as unknown as string; },
      (value) => { value.weather.retrieved_at = "2026-01-01T06:60:00Z"; },
    ];
    for (const mutate of mutations) {
      const invalid = structuredClone(targetPlan) as TargetPlan;
      mutate(invalid);
      vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response(invalid));
      await expect(getTargetPlan(targetPlan.target_plan_id)).rejects.toThrow("Invalid target plan response");
    }
  });
  it("accepts exact backend leap-day, UTC, offset, fractional, and naive timestamp forms", async () => {
    const valid = structuredClone(targetPlan) as TargetPlan;
    valid.window_start = "2024-02-29T06:00:00.123456+00:00";
    valid.window_end = "2024-02-29T08:00:00.123456Z";
    valid.candidates[0].latest_observation_at = "2024-02-29T01:00:00-07:00";
    valid.candidates[0].evidence_loaded_at = "2024-02-29T08:00:00";
    valid.evidence_freshness_at = valid.candidates[0].evidence_loaded_at;
    valid.weather.retrieved_at = "2024-02-29T08:00:00Z";
    valid.created_at = "2024-02-29T08:00:00+00:00";
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(valid));
    await expect(getTargetPlan(valid.target_plan_id)).resolves.toEqual(valid);
  });
  it("posts the exact selected origin without credentials", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(() => response(targetPlan));
    await createTargetPlan({ species_code: "target1", location: "Prescott", location_selection: { display_name: "Prescott, AZ", latitude: 34, longitude: -112, timezone: "America/Phoenix", region_code: "US-AZ", source: "open_meteo", source_id: "open_meteo_prescott", place_type: "Arizona place" }, radius_miles: 25, start_at: "2026-07-11T06:00:00", duration_minutes: 120 });
    const init = fetch.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body)).location_selection).toEqual({ display_name: "Prescott, AZ", latitude: 34, longitude: -112, timezone: "America/Phoenix", region_code: "US-AZ" });
    expect(String(init.body)).not.toMatch(/cloudflare|password|api.?key/i);
  });
  it("maps exact-shaped target errors to fixed text without rendering backend detail", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ error: { code: "not_found", message: "/private/target.duckdb raw-model secret" } }, false, 404));
    await expect(getTargetPlan(targetPlan.target_plan_id)).rejects.toThrow("Target plan not found.");
    await expect(getTargetPlan(targetPlan.target_plan_id)).rejects.not.toThrow(/private|raw-model|secret/);
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
