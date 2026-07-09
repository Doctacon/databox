import type { JsonObject } from "./types";

export interface WeatherPresentation {
  condition: string;
  elevation: string;
  metrics: Array<{ label: string; value: string }>;
}

const WMO_CONDITIONS: Readonly<Record<number, string>> = {
  0: "Clear",
  1: "Mainly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Fog",
  48: "Rime fog",
  51: "Light drizzle",
  53: "Drizzle",
  55: "Heavy drizzle",
  56: "Light freezing drizzle",
  57: "Heavy freezing drizzle",
  61: "Light rain",
  63: "Rain",
  65: "Heavy rain",
  66: "Light freezing rain",
  67: "Heavy freezing rain",
  71: "Light snow",
  73: "Snow",
  75: "Heavy snow",
  77: "Snow grains",
  80: "Light rain showers",
  81: "Rain showers",
  82: "Heavy rain showers",
  85: "Light snow showers",
  86: "Heavy snow showers",
  95: "Thunderstorm",
  96: "Thunderstorm with light hail",
  99: "Thunderstorm with heavy hail",
};

function object(value: unknown): JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as JsonObject
    : {};
}

function number(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function display(value: number, maximumFractionDigits: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits });
}

function temperature(value: unknown): string {
  const celsius = number(value);
  if (celsius === null) return "Not reported";
  const fahrenheit = celsius * 9 / 5 + 32;
  return `${display(fahrenheit, 1)}°F / ${display(celsius, 1)}°C`;
}

function speed(value: unknown): string {
  const kmh = number(value);
  if (kmh === null) return "Not reported";
  return `${display(kmh * 0.621371, 1)} mph / ${display(kmh, 1)} km/h`;
}

function precipitation(value: unknown): string {
  const millimeters = number(value);
  if (millimeters === null) return "Not reported";
  return `${display(millimeters * 0.0393701, 2)} in / ${display(millimeters, 1)} mm`;
}

function percent(value: unknown): string {
  const amount = number(value);
  return amount === null ? "Not reported" : `${display(amount, 0)}%`;
}

function elevation(value: unknown): string {
  const meters = number(value);
  if (meters === null) return "Not reported";
  return `${display(meters * 3.28084, 0)} ft / ${display(meters, 0)} m`;
}

function conditions(value: unknown): string {
  if (!Array.isArray(value)) return "Not reported";
  const labels = [...new Set(value.flatMap((code) => {
    const numericCode = number(code);
    if (numericCode === null) return [];
    return [WMO_CONDITIONS[numericCode] || "Unclassified conditions"];
  }))];
  if (labels.length === 0) return "Not reported";
  if (labels.length > 3) return `${labels.slice(0, 3).join(" · ")} · Mixed conditions`;
  return labels.join(" · ");
}

export function presentWeather(payload: JsonObject, evidenceSummary: JsonObject): WeatherPresentation {
  const forecast = Object.keys(object(payload.forecast_summary)).length > 0
    ? object(payload.forecast_summary)
    : object(evidenceSummary.forecast_summary);
  const elevationValue = payload.elevation_m ?? evidenceSummary.elevation_m;
  const condition = conditions(forecast.weather_codes);
  const elevationText = elevation(elevationValue);

  return {
    condition,
    elevation: elevationText,
    metrics: [
      { label: "Conditions", value: condition },
      { label: "Low temperature", value: temperature(forecast.temperature_2m_min) },
      { label: "High temperature", value: temperature(forecast.temperature_2m_max) },
      { label: "Average humidity", value: percent(forecast.relative_humidity_2m_avg) },
      { label: "Precipitation chance", value: percent(forecast.precipitation_probability_max) },
      { label: "Precipitation total", value: precipitation(forecast.precipitation_sum) },
      { label: "Maximum sustained wind", value: speed(forecast.wind_speed_10m_max) },
      { label: "Maximum gust", value: speed(forecast.wind_gusts_10m_max) },
      { label: "Elevation", value: elevationText },
    ],
  };
}
