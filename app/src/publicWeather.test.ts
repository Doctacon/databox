import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchPublicWeather, parsePublicWeatherSnapshot, publicWeatherEvidence } from "./publicWeather";

const workerUrl = "https://rufous-ai.loughondata.com";
const request = {
  latitude: 34.54123,
  longitude: -112.46872,
  start: "2026-08-10T13:30:00.000Z",
  end: "2026-08-10T15:00:00.000Z",
};

function forecast() {
  return {
    temperature_2m_min: 20,
    temperature_2m_max: 24,
    temperature_2m_avg: 22,
    relative_humidity_2m_avg: 40,
    precipitation_probability_max: 10,
    precipitation_sum: null,
    wind_speed_10m_max: 12.5,
    wind_gusts_10m_max: null,
    weather_codes: [],
    condition_summaries: ["Mostly Sunny"],
  };
}

function available() {
  return {
    status: "available",
    retrieved_at: "2026-08-08T15:00:00.000Z",
    forecast_summary: forecast(),
    elevation_m: 1_636.5,
    caveats: ["Forecasts can change."],
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("public NWS and USGS weather client", () => {
  it("accepts complete and single-provider partial responses in canonical SI units", () => {
    expect(parsePublicWeatherSnapshot(available())).toEqual(available());
    expect(parsePublicWeatherSnapshot({
      ...available(),
      status: "partial",
      forecast_summary: Object.fromEntries(Object.keys(forecast()).map((key) => [
        key,
        key === "weather_codes" || key === "condition_summaries" ? [] : null,
      ])),
    })).toMatchObject({ status: "partial", elevation_m: 1_636.5 });
    expect(parsePublicWeatherSnapshot({
      ...available(),
      status: "partial",
      elevation_m: null,
    })).toMatchObject({ status: "partial", elevation_m: null, forecast_summary: { condition_summaries: ["Mostly Sunny"] } });
  });

  it("rejects extra fields, impossible status relationships, unsafe values, and empty data", () => {
    expect(parsePublicWeatherSnapshot({ ...available(), extra: true })).toBeNull();
    expect(parsePublicWeatherSnapshot({ ...available(), status: "partial" })).toBeNull();
    expect(parsePublicWeatherSnapshot({ ...available(), elevation_m: 99_999 })).toBeNull();
    expect(parsePublicWeatherSnapshot({
      ...available(),
      status: "partial",
      elevation_m: null,
      forecast_summary: {
        ...Object.fromEntries(Object.keys(forecast()).map((key) => [
          key,
          key === "weather_codes" || key === "condition_summaries" ? [] : null,
        ])),
      },
    })).toBeNull();
  });

  it("calls only the exact Worker endpoint with rounded coordinates and a private browser request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(available()), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));

    await expect(fetchPublicWeather(request, workerUrl)).resolves.toEqual(available());
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [input, options] = fetchMock.mock.calls[0]!;
    const url = new URL(String(input));
    expect(`${url.origin}${url.pathname}`).toBe("https://rufous-ai.loughondata.com/v1/weather");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      latitude: "34.5412",
      longitude: "-112.4687",
      start: request.start,
      end: request.end,
    });
    expect(options).toMatchObject({ method: "GET", credentials: "omit", referrerPolicy: "no-referrer" });
    expect(options?.body).toBeUndefined();
  });

  it("fails closed without a request for missing or unreviewed configuration", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    await expect(fetchPublicWeather(request, undefined)).resolves.toBeNull();
    await expect(fetchPublicWeather(request, "https://attacker.example")).resolves.toBeNull();
    await expect(fetchPublicWeather(request, "https://rufous-ai.loughondata.com/v1/weather?debug=1")).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("turns provider, quota, oversized, and malformed responses into harmless unavailability", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    fetchMock.mockResolvedValueOnce(new Response("quota", { status: 429 }));
    await expect(fetchPublicWeather(request, workerUrl)).resolves.toBeNull();
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 200, headers: { "Content-Length": "99999" } }));
    await expect(fetchPublicWeather(request, workerUrl)).resolves.toBeNull();
    fetchMock.mockResolvedValueOnce(new Response("{", { status: 200 }));
    await expect(fetchPublicWeather(request, workerUrl)).resolves.toBeNull();
  });

  it("creates one provenance object for both the plan weather field and evidence list", () => {
    const snapshot = parsePublicWeatherSnapshot(available())!;
    expect(publicWeatherEvidence(snapshot, "weather_trip_fixture")).toEqual({
      evidence_id: "weather_trip_fixture",
      recommendation_id: null,
      source: "nws_usgs",
      source_table: "nws_hourly_forecast_usgs_epqs",
      source_record_id: null,
      evidence_type: "weather_elevation_context",
      status: "available",
      retrieved_at: available().retrieved_at,
      summary: { providers: "National Weather Service + USGS EPQS" },
      payload: { forecast_summary: forecast(), elevation_m: 1_636.5 },
      caveats: ["Forecasts can change."],
    });
  });
});
