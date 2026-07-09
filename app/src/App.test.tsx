import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { TripPlanDetail } from "./types";

const detail: TripPlanDetail = {
  plan: {
    trip_plan_id: "trip-1", requested_location: "Thumb Butte",
    normalized_location_name: "Thumb Butte, Prescott, AZ", latitude: 34.54,
    longitude: -112.47, region_code: "US-AZ", window_start: "2026-07-10T06:00:00",
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
  weather: { evidence_id: "weather-1", recommendation_id: null, source: "open_meteo", source_table: null, source_record_id: null, evidence_type: "weather", status: "available", retrieved_at: null, summary: {}, payload: { elevation_m: 1642 }, caveats: [] },
  media: [{ evidence_id: "media-1", recommendation_id: "rec-1", source: "xeno_canto", source_table: "recordings", source_record_id: "XC1", evidence_type: "media_context", status: "available", retrieved_at: null, summary: { english_name: "Mexican Jay", license: "CC BY", recording_url: "https://xeno-canto.org/1" }, payload: { recordist: "Ada Birder" }, caveats: [] }],
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
    const mediaLink = screen.getByRole("link", { name: /Mexican Jay/ });
    expect(mediaLink).toHaveAttribute("href", "https://xeno-canto.org/1");
    expect(mediaLink).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByText("Source: Xeno-canto · Recordist: Ada Birder · License: CC BY")).toBeVisible();
    expect(screen.getByText("Weather changes quickly")).toBeVisible();
    expect(screen.getByText(/normalize location/)).toBeVisible();
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
    unavailable.media = [sentinel];
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

  it("does not activate an unsafe persisted media URL", async () => {
    const unsafe = structuredClone(detail);
    unsafe.media[0].summary.recording_url = "javascript:alert(1)";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [unsafe.plan] })
        : response(unsafe),
    );
    render(<App />);
    expect(await screen.findByText("Source: Xeno-canto · Recordist: Ada Birder · License: CC BY")).toBeVisible();
    expect(screen.queryByRole("link", { name: /Mexican Jay/ })).not.toBeInTheDocument();
  });

  it("submits a bounded form and surfaces a friendly model-unavailable error", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => response({ plans: [] }))
      .mockImplementationOnce(() => response({ error: { code: "model_unavailable", message: "The configured model is unavailable" } }, 503));
    render(<App />);
    await screen.findByText("No trip selected");
    await user.type(screen.getByLabelText("Location"), "Thumb Butte");
    await user.type(screen.getByLabelText("Start date and time"), "2026-07-10T06:00");
    await user.click(screen.getByRole("button", { name: "Create trip plan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The configured model is unavailable");
    const submitted = JSON.parse(String(fetchMock.mock.calls[1][1]?.body));
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
