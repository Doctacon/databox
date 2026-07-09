import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { TripPlanDetail } from "./types";

const detail: TripPlanDetail = {
  plan: {
    trip_plan_id: "trip-1", requested_location: "Thumb Butte",
    normalized_location_name: "Thumb Butte, Prescott, AZ", latitude: 34.54,
    longitude: -112.47, region_code: "US-AZ", timezone: "America/Phoenix", window_start: "2026-07-10T06:00:00",
    window_end: "2026-07-10T07:30:00", duration_minutes: 90, skill_level: "beginner",
    constraints_text: "focus on calls", plan_status: "complete",
    field_plan_text: "Listen first. High-likelihood species: Mexican Jay. Uncommon but plausible targets: Zone-tailed Hawk.",
    caveats: ["Weather changes quickly"], created_at: "2026-07-09T12:00:00",
    updated_at: "2026-07-09T12:00:00",
  },
  recommendations: [
    { recommendation_id: "rec-1", species_code: "mexjay", common_name: "Mexican Jay", scientific_name: "Aphelocoma wollweberi", recommendation_group: "high_likelihood", rank_order: 1, confidence_label: "high", rationale_text: "Recent eBird evidence", caveats: [] },
    { recommendation_id: "rec-2", species_code: "zthawk", common_name: "Zone-tailed Hawk", scientific_name: "Buteo albonotatus", recommendation_group: "uncommon_plausible", rank_order: 1, confidence_label: "plausible", rationale_text: "GBIF context", caveats: [] },
  ],
  evidence: [{ evidence_id: "ev-1", recommendation_id: "rec-1", source: "ebird", source_table: "recent", source_record_id: "S1", evidence_type: "recent_observation", status: "available", retrieved_at: null, summary: { location_name: "Thumb Butte" }, payload: {}, caveats: [] }],
  weather: { evidence_id: "weather-1", recommendation_id: null, source: "open_meteo", source_table: null, source_record_id: null, evidence_type: "weather", status: "available", retrieved_at: null, summary: {}, payload: { elevation_m: 1642, forecast_summary: { temperature_2m_min: 20, temperature_2m_max: 23, relative_humidity_2m_avg: 55, precipitation_probability_max: 20, precipitation_sum: 0.3, wind_speed_10m_max: 7, wind_gusts_10m_max: 10, weather_codes: [0, 1, 2] } }, caveats: ["Forecast may change"] },
  media: [{ evidence_id: "media-1", recommendation_id: "rec-1", source_record_id: "XC1", recording_id: "1", status: "available", species_name: "Mexican Jay", recording_type: "call", quality: "A", recordist: "Ada Birder", license_text: "CC BY 4.0", license_url: "https://creativecommons.org/licenses/by/4.0/", source_url: "https://xeno-canto.org/1", audio_url: "https://xeno-canto.org/1/download", caveats: [] }],
  tool_traces: [{ tool_trace_id: "trace-1", step_order: 1, tool_name: "normalize_location", tool_status: "ok", started_at: null, completed_at: null, input: {}, output_summary: {}, caveats: [] }],
};

function response(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Birding Trip Copilot", () => {
  it("loads a persisted plan with evidence, media, caveats, and workflow", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/trip-plans") return response({ plans: [detail.plan] });
      return response(detail);
    });
    render(<App />);
    expect(screen.getByLabelText("Location")).toBeRequired();
    expect(await screen.findByRole("heading", { name: "Thumb Butte, Prescott, AZ" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "High-likelihood species" })).toBeVisible();
    expect(screen.getByText("Mexican Jay", { selector: "h3" })).toBeVisible();
    const audio = document.querySelector("audio");
    expect(audio).not.toBeNull();
    expect(audio).toHaveAttribute("controls");
    expect(audio).toHaveAttribute("preload", "none");
    expect(audio).not.toHaveAttribute("autoplay");
    expect(audio).toHaveAttribute("src", "https://xeno-canto.org/1/download");
    expect(audio).toHaveAccessibleName("Play Mexican Jay · call · Quality A");
    const sourceLink = screen.getByRole("link", { name: "View recording on Xeno-canto" });
    expect(sourceLink).toHaveAttribute("href", "https://xeno-canto.org/1");
    expect(sourceLink).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByText("Recordist: Ada Birder")).toBeVisible();
    const licenseLink = screen.getByRole("link", { name: "CC BY 4.0" });
    expect(licenseLink).toHaveAttribute("href", "https://creativecommons.org/licenses/by/4.0/");
    expect(screen.getByText("Weather changes quickly")).toBeVisible();
    expect(screen.getByText(/normalize location/)).toBeVisible();
    const weatherPanel = screen.getByRole("heading", { name: "Weather and elevation" }).closest("section");
    expect(weatherPanel).not.toBeNull();
    expect(within(weatherPanel!).getByText("Clear · Mainly clear · Partly cloudy")).toBeVisible();
    expect(within(weatherPanel!).getByText("68°F / 20°C")).toBeVisible();
    expect(within(weatherPanel!).getByText("73.4°F / 23°C")).toBeVisible();
    expect(within(weatherPanel!).getByText("4.3 mph / 7 km/h")).toBeVisible();
    expect(within(weatherPanel!).getByText("0.01 in / 0.3 mm")).toBeVisible();
    expect(within(weatherPanel!).getByText("Forecast may change")).toBeVisible();
    expect(within(weatherPanel!).getByText("Open-Meteo source status: available")).toBeVisible();
  });

  it("shows conformed common names as primary and scientific names as secondary", async () => {
    const conformed = structuredClone(detail);
    conformed.recommendations = [
      { recommendation_id: "rec-bluebird", species_code: "wesblu", common_name: "Western Bluebird", scientific_name: "Sialia mexicana", recommendation_group: "uncommon_plausible", rank_order: 1, confidence_label: "plausible", rationale_text: "GBIF context", caveats: [] },
      { recommendation_id: "rec-gila", species_code: "gilwoo", common_name: "Gila Woodpecker", scientific_name: "Melanerpes uropygialis", recommendation_group: "uncommon_plausible", rank_order: 2, confidence_label: "plausible", rationale_text: "GBIF context", caveats: [] },
      { recommendation_id: "rec-owl", species_code: "nswowl", common_name: "Northern Saw-whet Owl", scientific_name: "Aegolius acadicus", recommendation_group: "uncommon_plausible", rank_order: 3, confidence_label: "plausible", rationale_text: "GBIF context", caveats: [] },
      { recommendation_id: "rec-unknown", species_code: null, common_name: null, scientific_name: "Mysteria avis", recommendation_group: "uncommon_plausible", rank_order: 4, confidence_label: "plausible", rationale_text: "GBIF context", caveats: [] },
    ];
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [conformed.plan] }) : response(conformed),
    );

    render(<App />);
    for (const commonName of ["Western Bluebird", "Gila Woodpecker", "Northern Saw-whet Owl"]) {
      expect(await screen.findByRole("heading", { name: commonName, level: 3 })).toBeVisible();
    }
    for (const scientificName of ["Sialia mexicana", "Melanerpes uropygialis", "Aegolius acadicus"]) {
      expect(screen.getByText(scientificName)).toHaveClass("scientific");
    }
    expect(screen.getByRole("heading", { name: "Mysteria avis", level: 3 })).toBeVisible();
    expect(screen.queryByText("Mysteria avis", { selector: ".scientific" })).not.toBeInTheDocument();
  });

  it("keeps elevation and caveats visible when forecast fields are partial", async () => {
    const partial = structuredClone(detail);
    partial.weather!.status = "partial";
    partial.weather!.payload = { elevation_m: 1642 };
    partial.weather!.caveats = ["Open-Meteo forecast returned no hourly rows"];
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [partial.plan] }) : response(partial),
    );

    render(<App />);
    const weatherPanel = (await screen.findByRole("heading", { name: "Weather and elevation" })).closest("section");
    expect(weatherPanel).not.toBeNull();
    expect(within(weatherPanel!).getByText(/^5,?387 ft \/ 1,?642 m$/)).toBeVisible();
    expect(within(weatherPanel!).getAllByText("Not reported")).toHaveLength(8);
    expect(within(weatherPanel!).getByText("Open-Meteo forecast returned no hourly rows")).toBeVisible();
    expect(within(weatherPanel!).getByText("Open-Meteo source status: partial")).toBeVisible();
  });

  it("renders unavailable Xeno-canto evidence without treating its sentinel as media", async () => {
    const unavailable = structuredClone(detail);
    unavailable.plan.caveats = ["Xeno-canto evidence is unavailable"];
    const sentinel = {
      evidence_id: "media-unavailable", recommendation_id: null, source: "xeno_canto",
      source_table: null, source_record_id: null, evidence_type: "media_context",
      status: "unavailable", retrieved_at: null, summary: { status: "unavailable" }, payload: {},
      caveats: ["No Xeno-canto rows found"],
    };
    unavailable.evidence.push(sentinel);
    unavailable.media = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [unavailable.plan] })
        : response(unavailable),
    );
    render(<App />);
    expect(await screen.findByText("Xeno-canto evidence is unavailable")).toBeVisible();
    expect(screen.getByText("No Xeno-canto media examples were available.")).toBeVisible();
    expect(screen.getByText("unavailable", { selector: "td" })).toBeVisible();
    expect(screen.queryByRole("link", { name: /unavailable/i })).not.toBeInTheDocument();
  });

  it.each([
    ["javascript:alert(1)", "javascript:alert(2)"],
    ["https://evil.example/1", "https://evil.example/1/download"],
    ["https://user@xeno-canto.org/1", "https://user@xeno-canto.org/1/download"],
    ["https://xeno-canto.org:443/1", "https://xeno-canto.org:443/1/download"],
    ["https://media.xeno-canto.org/1", "https://media.xeno-canto.org/1/download"],
    ["https://xeno-canto.org/about", "https://xeno-canto.org/1/file.mp3"],
  ])("does not activate unsafe persisted source or audio URLs", async (sourceUrl, audioUrl) => {
    const unsafe = structuredClone(detail);
    unsafe.media[0].source_url = sourceUrl;
    unsafe.media[0].audio_url = audioUrl;
    unsafe.media[0].license_url = "javascript:alert(2)";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [unsafe.plan] })
        : response(unsafe),
    );
    render(<App />);
    expect(await screen.findByText("Recordist: Ada Birder")).toBeVisible();
    expect(document.querySelector(".media-license")).toHaveTextContent("License: CC BY 4.0");
    expect(screen.getByText("Audio playback is unavailable in the app.")).toBeVisible();
    expect(screen.getByText("Xeno-canto source page unavailable.")).toBeVisible();
    expect(document.querySelector("audio")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View recording on Xeno-canto" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "CC BY 4.0" })).not.toBeInTheDocument();
  });

  it.each([
    ["page/audio mismatch", "1", "https://xeno-canto.org/1", "https://xeno-canto.org/2/download", true, false],
    ["typed recording mismatch", "2", "https://xeno-canto.org/1", "https://xeno-canto.org/1/download", false, false],
    ["malformed typed recording id", "XC1", "https://xeno-canto.org/1", "https://xeno-canto.org/1/download", false, false],
    ["invalid audio with valid source", "1", "https://xeno-canto.org/1", "javascript:alert(1)", true, false],
    ["invalid source with valid audio", "1", "javascript:alert(1)", "https://xeno-canto.org/1/download", false, true],
  ])("validates source and audio independently for %s", async (_, recordingId, sourceUrl, audioUrl, hasSource, hasAudio) => {
    const mismatch = structuredClone(detail);
    mismatch.media[0].recording_id = recordingId;
    mismatch.media[0].source_url = sourceUrl;
    mismatch.media[0].audio_url = audioUrl;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [mismatch.plan] })
        : response(mismatch),
    );

    render(<App />);
    expect(await screen.findByText("Recordist: Ada Birder")).toBeVisible();
    if (hasAudio) {
      expect(document.querySelector("audio")).toHaveAttribute("src", audioUrl);
      expect(screen.queryByText("Audio playback is unavailable in the app.")).not.toBeInTheDocument();
    } else {
      expect(document.querySelector("audio")).not.toBeInTheDocument();
      expect(screen.getByText("Audio playback is unavailable in the app.")).toBeVisible();
    }
    if (hasSource) {
      expect(screen.getByRole("link", { name: "View recording on Xeno-canto" })).toHaveAttribute("href", sourceUrl);
      expect(screen.queryByText("Xeno-canto source page unavailable.")).not.toBeInTheDocument();
    } else {
      expect(screen.queryByRole("link", { name: "View recording on Xeno-canto" })).not.toBeInTheDocument();
      expect(screen.getByText("Xeno-canto source page unavailable.")).toBeVisible();
    }
  });

  it.each([
    "https://xeno-canto.org/1/../2",
    "https://xeno-canto.org/1/%2e%2e/2",
  ])("rejects raw traversal before URL normalization: %s", async (sourceUrl) => {
    const traversal = structuredClone(detail);
    traversal.media[0].recording_id = "2";
    traversal.media[0].source_url = sourceUrl;
    traversal.media[0].audio_url = "https://xeno-canto.org/2/download";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [traversal.plan] })
        : response(traversal),
    );

    render(<App />);
    expect(await screen.findByText("Recordist: Ada Birder")).toBeVisible();
    expect(document.querySelector("audio")).toHaveAttribute(
      "src",
      "https://xeno-canto.org/2/download",
    );
    expect(screen.queryByRole("link", { name: "View recording on Xeno-canto" })).not.toBeInTheDocument();
    expect(screen.getByText("Xeno-canto source page unavailable.")).toBeVisible();
  });

  it("retains attribution for missing audio and a safe source after runtime failure", async () => {
    const missing = structuredClone(detail);
    missing.media[0].audio_url = null;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [missing.plan] }) : response(missing),
    );
    const { unmount } = render(<App />);
    expect(await screen.findByText("Audio playback is unavailable in the app.")).toBeVisible();
    expect(screen.getByText("Recordist: Ada Birder")).toBeVisible();
    expect(screen.getByRole("link", { name: "View recording on Xeno-canto" })).toHaveAttribute(
      "href",
      "https://xeno-canto.org/1",
    );
    expect(screen.queryByText("Xeno-canto source page unavailable.")).not.toBeInTheDocument();
    unmount();

    const failed = structuredClone(detail);
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [failed.plan] }) : response(failed),
    );
    render(<App />);
    const audio = await waitFor(() => {
      const element = document.querySelector("audio");
      expect(element).not.toBeNull();
      return element!;
    });
    fireEvent.error(audio);
    expect(await screen.findByText("Audio playback is unavailable in the app.")).toBeVisible();
    expect(screen.getByText("Recordist: Ada Birder")).toBeVisible();
    expect(screen.getByRole("link", { name: "View recording on Xeno-canto" })).toBeVisible();
  });

  it("searches Arizona places and supports keyboard selection", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url === "/api/trip-plans" && init?.method === "POST") return response(detail, 201);
      if (url.startsWith("/api/locations")) {
        return response({
          locations: [{
            display_name: "Prescott, Arizona, United States",
            latitude: 34.54002,
            longitude: -112.4685,
            timezone: "America/Phoenix",
            region_code: "US-AZ",
          }],
        });
      }
      return response({ plans: [] });
    });
    render(<App />);
    await screen.findByText("No trip selected");
    const location = screen.getByRole("combobox", { name: "Location" });
    await user.type(location, "Prescott, Arizona");
    const option = await screen.findByRole("option", { name: /Prescott, Arizona, United States/ });
    expect(location).toHaveAttribute("aria-expanded", "true");
    expect(option).toBeVisible();
    await user.keyboard("{ArrowDown}{Enter}");
    expect(location).toHaveValue("Prescott, Arizona, United States");
    expect(location).toHaveAttribute("aria-expanded", "false");
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes("Prescott%2C%20Arizona"))).toBe(true);
    await user.type(screen.getByLabelText("Start date and time"), "2026-07-10T06:00");
    await user.click(screen.getByRole("button", { name: "Create trip plan" }));
    await screen.findByRole("heading", { name: "Thumb Butte, Prescott, AZ" });
    const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(postCall?.[1]?.body))).toMatchObject({
      location: "Prescott, Arizona, United States",
      location_selection: {
        display_name: "Prescott, Arizona, United States",
        latitude: 34.54002,
        longitude: -112.4685,
        timezone: "America/Phoenix",
        region_code: "US-AZ",
      },
    });
  });

  it("cancels stale location searches and lets coordinates bypass geocoding", async () => {
    const user = userEvent.setup();
    const signals: AbortSignal[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.startsWith("/api/locations")) {
        if (init?.signal) signals.push(init.signal);
        return new Promise(() => undefined);
      }
      return response({ plans: [] });
    });
    render(<App />);
    await screen.findByText("No trip selected");
    const location = screen.getByRole("combobox", { name: "Location" });
    await user.type(location, "Pres");
    await waitFor(() => expect(signals).toHaveLength(1));
    await user.type(location, "cott");
    await waitFor(() => expect(signals[0].aborted).toBe(true));
    await user.clear(location);
    await user.type(location, "34.54,-112.47");
    await new Promise((resolve) => window.setTimeout(resolve, 300));
    expect(signals).toHaveLength(1);
  });

  it("surfaces geocoder failure while preserving coordinate entry", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      if (String(input).startsWith("/api/locations")) {
        return response({
          error: {
            code: "geocoder_unavailable",
            message: "Location search is temporarily unavailable; enter valid Arizona coordinates",
          },
        }, 503);
      }
      return response({ plans: [] });
    });
    render(<App />);
    await screen.findByText("No trip selected");
    const location = screen.getByRole("combobox", { name: "Location" });
    await user.type(location, "Prescott");
    expect(await screen.findByText(/Location search is temporarily unavailable/)).toBeVisible();
    await user.clear(location);
    await user.type(location, "34.54,-112.47");
    expect(location).toHaveValue("34.54,-112.47");
  });

  it("submits a bounded form and surfaces a friendly model-unavailable error", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockImplementation((input, init) => {
        const url = String(input);
        if (url.startsWith("/api/locations")) return response({ locations: [] });
        if (url === "/api/trip-plans" && init?.method === "POST") {
          return response({ error: { code: "model_unavailable", message: "The configured model is unavailable" } }, 503);
        }
        return response({ plans: [] });
      });
    render(<App />);
    await screen.findByText("No trip selected");
    await user.type(screen.getByLabelText("Location"), "Thumb Butte");
    await user.type(screen.getByLabelText("Start date and time"), "2026-07-10T06:00");
    await user.click(screen.getByRole("button", { name: "Create trip plan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The configured model is unavailable");
    const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const submitted = JSON.parse(String(postCall?.[1]?.body));
    expect(submitted).toMatchObject({ location: "Thumb Butte", duration_minutes: 90 });
  });

  it("surfaces a friendly database-busy state", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({
      error: { code: "database_busy", message: "The warehouse is refreshing; try again shortly" },
    }, 503));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The warehouse is refreshing; try again shortly");
  });

  it("shows a readable empty state when there are no saved plans", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ plans: [] }));
    render(<App />);
    await waitFor(() => expect(screen.getByText("No trip selected")).toBeVisible());
    expect(screen.getByText(/Create a plan or choose a saved plan/)).toBeVisible();
  });
});
