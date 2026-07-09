import { describe, expect, it } from "vitest";
import { presentWeather } from "./weather";

describe("weather presentation", () => {
  it("converts every persisted forecast measurement into both unit systems", () => {
    const weather = presentWeather({
      elevation_m: 1642,
      forecast_summary: {
        temperature_2m_min: 20,
        temperature_2m_max: 23,
        relative_humidity_2m_avg: 55,
        precipitation_probability_max: 20,
        precipitation_sum: 0.3,
        wind_speed_10m_max: 7,
        wind_gusts_10m_max: 10,
        weather_codes: [0, 1, 2],
      },
    }, {});

    expect(weather.condition).toBe("Clear · Mainly clear · Partly cloudy");
    expect(weather.elevation).toMatch(/^5,?387 ft \/ 1,?642 m$/);
    expect(Object.fromEntries(weather.metrics.map((metric) => [metric.label, metric.value]))).toEqual({
      Conditions: "Clear · Mainly clear · Partly cloudy",
      "Low temperature": "68°F / 20°C",
      "High temperature": "73.4°F / 23°C",
      "Average humidity": "55%",
      "Precipitation chance": "20%",
      "Precipitation total": "0.01 in / 0.3 mm",
      "Maximum sustained wind": "4.3 mph / 7 km/h",
      "Maximum gust": "6.2 mph / 10 km/h",
      Elevation: weather.elevation,
    });
  });

  it("keeps partial values visible and labels each missing field", () => {
    const weather = presentWeather({ elevation_m: 1642 }, {});
    const metrics = Object.fromEntries(weather.metrics.map((metric) => [metric.label, metric.value]));

    expect(metrics.Elevation).toMatch(/^5,?387 ft \/ 1,?642 m$/);
    expect(metrics.Conditions).toBe("Not reported");
    expect(metrics["Low temperature"]).toBe("Not reported");
    expect(metrics["Precipitation total"]).toBe("Not reported");
    expect(metrics["Maximum gust"]).toBe("Not reported");
  });

  it("bounds long or unknown WMO code sets", () => {
    const weather = presentWeather({
      forecast_summary: { weather_codes: [0, 1, 2, 3, 123] },
    }, {});

    expect(weather.condition).toBe("Clear · Mainly clear · Partly cloudy · Mixed conditions");
  });
});
