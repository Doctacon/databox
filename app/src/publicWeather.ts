import type { Evidence } from "./types";

const PRODUCTION_WORKER_HOST = "rufous-ai.loughondata.com";
const WEATHER_PATH = "/v1/weather";
const WEATHER_TIMEOUT_MS = 10_000;
const MAX_RESPONSE_BYTES = 24 * 1024;

const FORECAST_KEYS = [
  "temperature_2m_min",
  "temperature_2m_max",
  "temperature_2m_avg",
  "relative_humidity_2m_avg",
  "precipitation_probability_max",
  "precipitation_sum",
  "wind_speed_10m_max",
  "wind_gusts_10m_max",
  "weather_codes",
  "condition_summaries",
] as const;

interface ForecastSummary {
  temperature_2m_min: number | null;
  temperature_2m_max: number | null;
  temperature_2m_avg: number | null;
  relative_humidity_2m_avg: number | null;
  precipitation_probability_max: number | null;
  precipitation_sum: number | null;
  wind_speed_10m_max: number | null;
  wind_gusts_10m_max: number | null;
  weather_codes: number[];
  condition_summaries: string[];
}

export interface PublicWeatherSnapshot {
  status: "available" | "partial";
  retrieved_at: string;
  forecast_summary: ForecastSummary;
  elevation_m: number | null;
  caveats: string[];
}

export interface PublicWeatherRequest {
  latitude: number;
  longitude: number;
  start: string;
  end: string;
}

function exactRecord(value: unknown, keys: readonly string[]): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const row = value as Record<string, unknown>;
  const actual = Object.keys(row).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index])
    ? row
    : null;
}

function boundedNumber(value: unknown, minimum: number, maximum: number): number | null | undefined {
  if (value === null) return null;
  return typeof value === "number" && Number.isFinite(value) && value >= minimum && value <= maximum
    ? value
    : undefined;
}

function validTimestamp(value: unknown): value is string {
  return typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value)
    && !Number.isNaN(Date.parse(value));
}

function parseForecast(value: unknown): ForecastSummary | null {
  const row = exactRecord(value, FORECAST_KEYS);
  if (!row) return null;
  const temperatureMin = boundedNumber(row.temperature_2m_min, -100, 70);
  const temperatureMax = boundedNumber(row.temperature_2m_max, -100, 70);
  const temperatureAvg = boundedNumber(row.temperature_2m_avg, -100, 70);
  const humidity = boundedNumber(row.relative_humidity_2m_avg, 0, 100);
  const precipitationProbability = boundedNumber(row.precipitation_probability_max, 0, 100);
  const precipitation = boundedNumber(row.precipitation_sum, 0, 1_000);
  const wind = boundedNumber(row.wind_speed_10m_max, 0, 500);
  const gusts = boundedNumber(row.wind_gusts_10m_max, 0, 500);
  if (temperatureMin === undefined || temperatureMax === undefined || temperatureAvg === undefined
    || humidity === undefined || precipitationProbability === undefined || precipitation === undefined
    || wind === undefined || gusts === undefined) return null;
  if (!Array.isArray(row.weather_codes) || row.weather_codes.length > 16
    || row.weather_codes.some((item) => !Number.isSafeInteger(item) || item < 0 || item > 999)) return null;
  if (!Array.isArray(row.condition_summaries) || row.condition_summaries.length > 3
    || row.condition_summaries.some((item) => typeof item !== "string"
      || item.length < 1 || item.length > 80 || /[\u0000-\u001f\u007f]/.test(item))) return null;
  const hasForecast = [temperatureMin, temperatureMax, temperatureAvg, humidity, precipitationProbability, wind, gusts]
    .some((item) => item !== null) || row.weather_codes.length > 0 || row.condition_summaries.length > 0;
  if (!hasForecast) return null;
  if (temperatureMin !== null && temperatureMax !== null && temperatureMin > temperatureMax) return null;
  return {
    temperature_2m_min: temperatureMin as number | null,
    temperature_2m_max: temperatureMax as number | null,
    temperature_2m_avg: temperatureAvg as number | null,
    relative_humidity_2m_avg: humidity as number | null,
    precipitation_probability_max: precipitationProbability as number | null,
    precipitation_sum: precipitation as number | null,
    wind_speed_10m_max: wind as number | null,
    wind_gusts_10m_max: gusts as number | null,
    weather_codes: [...row.weather_codes] as number[],
    condition_summaries: [...row.condition_summaries] as string[],
  };
}

export function parsePublicWeatherSnapshot(value: unknown): PublicWeatherSnapshot | null {
  const row = exactRecord(value, ["status", "retrieved_at", "forecast_summary", "elevation_m", "caveats"]);
  if (!row || (row.status !== "available" && row.status !== "partial") || !validTimestamp(row.retrieved_at)) return null;
  const forecast = parseForecast(row.forecast_summary);
  const elevation = boundedNumber(row.elevation_m, -200, 5_000);
  if (elevation === undefined || !Array.isArray(row.caveats) || row.caveats.length > 8
    || row.caveats.some((item) => typeof item !== "string" || item.length < 1 || item.length > 300
      || /[\u0000-\u001f\u007f]/.test(item))) return null;
  const expectedStatus = forecast !== null && elevation !== null ? "available" : "partial";
  if (row.status !== expectedStatus || (forecast === null && elevation === null)) return null;
  return {
    status: row.status,
    retrieved_at: row.retrieved_at,
    forecast_summary: forecast ?? {
      temperature_2m_min: null,
      temperature_2m_max: null,
      temperature_2m_avg: null,
      relative_humidity_2m_avg: null,
      precipitation_probability_max: null,
      precipitation_sum: null,
      wind_speed_10m_max: null,
      wind_gusts_10m_max: null,
      weather_codes: [],
      condition_summaries: [],
    },
    elevation_m: elevation,
    caveats: [...row.caveats] as string[],
  };
}

function weatherEndpoint(raw: unknown): URL | null {
  if (typeof raw !== "string" || raw.length === 0) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:" || url.hostname !== PRODUCTION_WORKER_HOST
      || url.username || url.password || url.port || url.search || url.hash
      || (url.pathname !== "/" && url.pathname !== "/v1/ai/enrich" && url.pathname !== WEATHER_PATH)) return null;
    url.pathname = WEATHER_PATH;
    return url;
  } catch {
    return null;
  }
}

export async function fetchPublicWeather(
  input: PublicWeatherRequest,
  rawWorkerUrl: unknown = import.meta.env.VITE_RUFOUS_AI_URL,
): Promise<PublicWeatherSnapshot | null> {
  const url = weatherEndpoint(rawWorkerUrl);
  if (!url || !Number.isFinite(input.latitude) || !Number.isFinite(input.longitude)
    || !validTimestamp(input.start) || !validTimestamp(input.end)
    || Date.parse(input.end) <= Date.parse(input.start)) return null;
  url.searchParams.set("latitude", input.latitude.toFixed(4));
  url.searchParams.set("longitude", input.longitude.toFixed(4));
  url.searchParams.set("start", input.start);
  url.searchParams.set("end", input.end);

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), WEATHER_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "omit",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
    });
    if (!response.ok) return null;
    const declaredLength = response.headers.get("Content-Length");
    if (declaredLength !== null && (!/^\d+$/.test(declaredLength) || Number(declaredLength) > MAX_RESPONSE_BYTES)) return null;
    const text = await response.text();
    if (new TextEncoder().encode(text).byteLength > MAX_RESPONSE_BYTES) return null;
    return parsePublicWeatherSnapshot(JSON.parse(text) as unknown);
  } catch {
    return null;
  } finally {
    window.clearTimeout(timeout);
  }
}

export function publicWeatherEvidence(
  snapshot: PublicWeatherSnapshot,
  evidenceId: string,
): Evidence {
  return {
    evidence_id: evidenceId,
    recommendation_id: null,
    source: "nws_usgs",
    source_table: "nws_hourly_forecast_usgs_epqs",
    source_record_id: null,
    evidence_type: "weather_elevation_context",
    status: snapshot.status,
    retrieved_at: snapshot.retrieved_at,
    summary: { providers: "National Weather Service + USGS EPQS" },
    payload: {
      forecast_summary: snapshot.forecast_summary,
      elevation_m: snapshot.elevation_m,
    },
    caveats: [...snapshot.caveats],
  };
}
