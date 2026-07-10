import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { Evidence, Recommendation, RecommendationCall, RecommendationPhoto, TripPlanDetail } from "./types";

const unavailablePhoto: RecommendationPhoto = {
  status: "unavailable", source_record_id: null, species_name: null, display_url: null,
  source_url: null, creator: null, rights_holder: null, publisher: null, format: null,
  license_text: null, license_url: null, selection_reason: null, caveats: [],
};
const unavailableCall: RecommendationCall = {
  status: "unavailable", source_record_id: null, recording_id: null, species_name: null,
  geographic_scope: null, recording_type: null, quality: null, recordist: null,
  locality: null, country: null, source_url: null, audio_url: null, license_text: null,
  license_url: null, selection_reason: null, caveats: [],
};
const availablePhoto: RecommendationPhoto = {
  status: "available", source_record_id: "5938231789", species_name: "Aphelocoma wollweberi",
  display_url: "https://api.gbif.org/v1/image/cache/500x500/occurrence/5938231789/media/0123456789abcdef0123456789abcdef",
  source_url: "https://www.gbif.org/occurrence/5938231789", creator: "Pat Photographer",
  rights_holder: "Arizona Bird Archive", publisher: "GBIF Fixture Publisher", format: "image/jpeg",
  license_text: "CC BY 4.0", license_url: "https://creativecommons.org/licenses/by/4.0/",
  selection_reason: "Fixture", caveats: [],
};
const availableCall: RecommendationCall = {
  status: "available", source_record_id: "1", recording_id: "1",
  species_name: "Aphelocoma wollweberi", geographic_scope: "Arizona", recording_type: "call",
  quality: "A", recordist: "Ada Birder", locality: "Prescott, Arizona", country: "United States",
  source_url: "https://xeno-canto.org/1", audio_url: "https://xeno-canto.org/1/download",
  license_text: "CC BY 4.0", license_url: "https://creativecommons.org/licenses/by/4.0/",
  selection_reason: "Fixture", caveats: [],
};

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
    { recommendation_id: "rec-1", species_code: "mexjay", common_name: "Mexican Jay", scientific_name: "Aphelocoma wollweberi", recommendation_group: "high_likelihood", rank_order: 1, confidence_label: "high", rationale_text: "Recent eBird evidence", caveats: [], photo: availablePhoto, call: availableCall },
    { recommendation_id: "rec-2", species_code: "zthawk", common_name: "Zone-tailed Hawk", scientific_name: "Buteo albonotatus", recommendation_group: "uncommon_plausible", rank_order: 1, confidence_label: "plausible", rationale_text: "GBIF context", caveats: [], photo: unavailablePhoto, call: unavailableCall },
  ],
  evidence: [{ evidence_id: "ev-1", recommendation_id: "rec-1", source: "ebird", source_table: "recent", source_record_id: "S1", evidence_type: "recent_observation", status: "available", retrieved_at: null, summary: { location_name: "Thumb Butte" }, payload: {}, caveats: [] }],
  weather: { evidence_id: "weather-1", recommendation_id: null, source: "open_meteo", source_table: null, source_record_id: null, evidence_type: "weather", status: "available", retrieved_at: null, summary: {}, payload: { elevation_m: 1642, forecast_summary: { temperature_2m_min: 20, temperature_2m_max: 23, relative_humidity_2m_avg: 55, precipitation_probability_max: 20, precipitation_sum: 0.3, wind_speed_10m_max: 7, wind_gusts_10m_max: 10, weather_codes: [0, 1, 2] } }, caveats: ["Forecast may change"] },
  media: [{ evidence_id: "media-1", recommendation_id: "rec-1", source_record_id: "XC1", recording_id: "1", status: "available", species_name: "Mexican Jay", recording_type: "call", quality: "A", recordist: "Ada Birder", license_text: "CC BY 4.0", license_url: "https://creativecommons.org/licenses/by/4.0/", source_url: "https://xeno-canto.org/1", audio_url: "https://xeno-canto.org/1/download", caveats: [] }],
  tool_traces: [{ tool_trace_id: "trace-1", step_order: 1, tool_name: "normalize_location", tool_status: "ok", started_at: null, completed_at: null, input: {}, output_summary: {}, caveats: [] }],
};

function response(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

function recommendation(group: "high_likelihood" | "uncommon_plausible", index: number): Recommendation {
  const prefix = group === "high_likelihood" ? "High" : "Uncommon";
  return {
    recommendation_id: `${group}-${index}`,
    species_code: `${prefix.toLowerCase()}-${index}`,
    common_name: `${prefix} Bird ${index}`,
    scientific_name: `Avis ${prefix.toLowerCase()}-${index}`,
    recommendation_group: group,
    rank_order: group === "high_likelihood" ? index : 100 + index,
    confidence_label: "evidence-backed",
    rationale_text: `${prefix} rationale ${index}`,
    caveats: [],
    photo: unavailablePhoto,
    call: unavailableCall,
  };
}

function evidenceRow(index: number): Evidence {
  return {
    evidence_id: `evidence-${index}`,
    recommendation_id: null,
    source: `source-${index}`,
    source_table: null,
    source_record_id: `record-${index}`,
    evidence_type: `evidence_type_${index}`,
    status: "available",
    retrieved_at: null,
    summary: { location_name: `Evidence Place ${index}` },
    payload: {},
    caveats: [],
  };
}

function paginatedDetail(
  planId: string,
  highCount: number,
  uncommonCount: number,
  evidenceCount: number,
): TripPlanDetail {
  const result = structuredClone(detail);
  result.plan.trip_plan_id = planId;
  result.plan.normalized_location_name = `Plan ${planId}`;
  result.recommendations = [
    ...Array.from({ length: highCount }, (_, index) => recommendation("high_likelihood", index + 1)),
    ...Array.from({ length: uncommonCount }, (_, index) => recommendation("uncommon_plausible", index + 1)),
  ];
  result.evidence = Array.from({ length: evidenceCount }, (_, index) => evidenceRow(index + 1));
  return result;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Birding Trip Copilot", () => {
  it("renders exact result order with recommendation media and final workflow disclosure", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/trip-plans") return response({ plans: [detail.plan] });
      return response(detail);
    });
    render(<App />);
    expect(screen.getByLabelText("Location")).toBeRequired();
    expect(await screen.findByRole("heading", { name: "Thumb Butte, Prescott, AZ" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "High-likelihood Species" })).toBeVisible();
    expect(screen.getByText("Mexican Jay", { selector: "h3" })).toBeVisible();
    const panelHeadings = Array.from(document.querySelectorAll(".plan > .panel"))
      .map((panel) => panel.querySelector("h2")?.textContent);
    expect(panelHeadings).toEqual([
      "Field Plan",
      "Weather and Elevation",
      "High-likelihood Species",
      "Uncommon but Plausible Targets",
      "Evidence and Provenance",
    ]);
    expect(document.querySelector(".plan")?.lastElementChild).toContainElement(
      screen.getByRole("heading", { name: "Evidence and Provenance" }),
    );
    expect(screen.queryByRole("heading", { name: /Call and media examples/i })).not.toBeInTheDocument();
    const photo = screen.getByRole("img", { name: "Mexican Jay (Aphelocoma wollweberi)" });
    expect(photo).toHaveAttribute("loading", "lazy");
    expect(photo).toHaveClass("responsive-bird-photo");
    expect(photo.closest(".photo-frame")).not.toBeNull();
    expect(photo).not.toHaveAttribute("width");
    expect(photo).not.toHaveAttribute("height");
    expect(photo).toHaveAttribute("src", availablePhoto.display_url);
    const unavailableCard = document.querySelector<HTMLElement>('[data-recommendation-id="rec-2"]');
    expect(unavailableCard).not.toBeNull();
    expect(within(unavailableCard!).getByText("No licensed photo is available.")).toBeVisible();
    expect(within(unavailableCard!).getByText("No licensed call example is available.")).toBeVisible();
    const audio = document.querySelector("audio");
    expect(audio).not.toBeNull();
    expect(audio).toHaveAttribute("controls");
    expect(audio).toHaveAttribute("preload", "none");
    expect(audio).not.toHaveAttribute("autoplay");
    expect(audio).toHaveAttribute("src", "https://xeno-canto.org/1/download");
    expect(audio).toHaveAccessibleName("Play Mexican Jay · call · Quality A");
    const sourceLink = screen.getByRole("link", { name: "View call source on Xeno-canto" });
    expect(sourceLink).toHaveAttribute("href", "https://xeno-canto.org/1");
    expect(sourceLink).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByText("Arizona recording")).toBeVisible();
    expect(screen.getByText("Recordist: Ada Birder")).toBeVisible();
    expect(screen.getByText("Creator: Pat Photographer")).toBeVisible();
    expect(screen.getByText("Rights holder: Arizona Bird Archive")).toBeVisible();
    expect(screen.getByText("Publisher: GBIF Fixture Publisher")).toBeVisible();
    expect(screen.getAllByRole("link", { name: "CC BY 4.0" })).toHaveLength(2);
    expect(screen.getByRole("link", { name: "View photo source on GBIF" })).toHaveAttribute(
      "href", availablePhoto.source_url,
    );
    expect(screen.getByText("Weather changes quickly")).toBeVisible();
    const evidenceSummary = screen.getByText("Evidence and Provenance").closest("summary");
    const evidenceDisclosure = evidenceSummary?.closest("details");
    expect(evidenceDisclosure).not.toHaveAttribute("open");
    expect(screen.getByText("recent observation")).not.toBeVisible();
    fireEvent.click(evidenceSummary!);
    expect(evidenceDisclosure).toHaveAttribute("open");
    expect(screen.getByText("recent observation")).toBeVisible();
    const workflowSummary = screen.getByText("Agent Workflow");
    expect(workflowSummary.tagName).toBe("SUMMARY");
    const workflow = workflowSummary.closest("details");
    expect(workflow).not.toHaveAttribute("open");
    fireEvent.click(workflowSummary);
    expect(workflow).toHaveAttribute("open");
    expect(screen.getByText(/normalize location/)).toBeVisible();
    const weatherPanel = screen.getByRole("heading", { name: "Weather and Elevation" }).closest("section");
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
      { recommendation_id: "rec-bluebird", species_code: "wesblu", common_name: "Western Bluebird", scientific_name: "Sialia mexicana", recommendation_group: "uncommon_plausible", rank_order: 1, confidence_label: "plausible", rationale_text: "GBIF context", caveats: [], photo: unavailablePhoto, call: unavailableCall },
      { recommendation_id: "rec-gila", species_code: "gilwoo", common_name: "Gila Woodpecker", scientific_name: "Melanerpes uropygialis", recommendation_group: "uncommon_plausible", rank_order: 2, confidence_label: "plausible", rationale_text: "GBIF context", caveats: [], photo: unavailablePhoto, call: unavailableCall },
      { recommendation_id: "rec-owl", species_code: "nswowl", common_name: "Northern Saw-whet Owl", scientific_name: "Aegolius acadicus", recommendation_group: "uncommon_plausible", rank_order: 3, confidence_label: "plausible", rationale_text: "GBIF context", caveats: [], photo: unavailablePhoto, call: unavailableCall },
      { recommendation_id: "rec-unknown", species_code: null, common_name: null, scientific_name: "Mysteria avis", recommendation_group: "uncommon_plausible", rank_order: 4, confidence_label: "plausible", rationale_text: "GBIF context", caveats: [], photo: unavailablePhoto, call: unavailableCall },
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
    const weatherPanel = (await screen.findByRole("heading", { name: "Weather and Elevation" })).closest("section");
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
    unavailable.recommendations[0].call = unavailableCall;
    unavailable.media = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [unavailable.plan] })
        : response(unavailable),
    );
    render(<App />);
    expect(await screen.findByText("Xeno-canto evidence is unavailable")).toBeVisible();
    expect(screen.getAllByText("No licensed call example is available.")).toHaveLength(2);
    expect(screen.queryByRole("heading", { name: /Call and media examples/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Evidence and Provenance").closest("summary")!);
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
    unsafe.recommendations[0].call.source_url = sourceUrl;
    unsafe.recommendations[0].call.audio_url = audioUrl;
    unsafe.recommendations[0].call.license_url = "javascript:alert(2)";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [unsafe.plan] })
        : response(unsafe),
    );
    render(<App />);
    expect(await screen.findByText("Recordist: Ada Birder")).toBeVisible();
    const callArea = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"] .recommendation-call');
    expect(callArea).not.toBeNull();
    expect(within(callArea!).getByText(/License:/)).toHaveTextContent("License: unavailable");
    expect(within(callArea!).getByText("No licensed call example is available.")).toBeVisible();
    expect(within(callArea!).getByText("Xeno-canto source page unavailable.")).toBeVisible();
    expect(within(callArea!).queryByRole("link", { name: "View call source on Xeno-canto" })).not.toBeInTheDocument();
    expect(within(callArea!).queryByRole("link", { name: "CC BY 4.0" })).not.toBeInTheDocument();
    expect(document.querySelector("audio")).not.toBeInTheDocument();
  });

  it.each([
    ["page/audio mismatch", "1", "https://xeno-canto.org/1", "https://xeno-canto.org/2/download", false, false, false],
    ["typed recording mismatch", "2", "https://xeno-canto.org/1", "https://xeno-canto.org/1/download", false, false, false],
    ["malformed typed recording id", "XC1", "https://xeno-canto.org/1", "https://xeno-canto.org/1/download", false, false, false],
    ["invalid audio with valid source", "1", "https://xeno-canto.org/1", "javascript:alert(1)", true, false, true],
    ["invalid source with valid audio", "1", "javascript:alert(1)", "https://xeno-canto.org/1/download", false, true, true],
  ])("validates source and audio independently for %s", async (_, recordingId, sourceUrl, audioUrl, hasSource, hasAudio, hasMetadata) => {
    const mismatch = structuredClone(detail);
    mismatch.recommendations[0].call.recording_id = recordingId;
    mismatch.recommendations[0].call.source_url = sourceUrl;
    mismatch.recommendations[0].call.audio_url = audioUrl;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [mismatch.plan] })
        : response(mismatch),
    );

    render(<App />);
    await screen.findByRole("heading", { name: "Mexican Jay" });
    const card = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"]');
    const callArea = card!.querySelector<HTMLElement>(".recommendation-call");
    if (hasMetadata) {
      expect(within(callArea!).getByText("Recordist: Ada Birder")).toBeVisible();
    } else {
      expect(within(callArea!).queryByText("Recordist: Ada Birder")).not.toBeInTheDocument();
      expect(within(callArea!).getByText("Call metadata did not match this recommendation.")).toBeVisible();
    }
    if (hasSource && hasAudio) {
      expect(document.querySelector("audio")).toHaveAttribute("src", audioUrl);
    } else {
      expect(document.querySelector("audio")).not.toBeInTheDocument();
      expect(screen.getAllByText("No licensed call example is available.").length).toBeGreaterThan(0);
    }
    if (hasSource) {
      expect(within(callArea!).getByRole("link", { name: "View call source on Xeno-canto" })).toHaveAttribute("href", sourceUrl);
      expect(within(callArea!).queryByText("Xeno-canto source page unavailable.")).not.toBeInTheDocument();
    } else {
      expect(within(callArea!).queryByRole("link", { name: "View call source on Xeno-canto" })).not.toBeInTheDocument();
      if (hasMetadata) {
        expect(within(callArea!).getByText("Xeno-canto source page unavailable.")).toBeVisible();
      } else {
        expect(within(callArea!).queryByText("Xeno-canto source page unavailable.")).not.toBeInTheDocument();
      }
    }
  });

  it.each([
    "https://xeno-canto.org/1/../2",
    "https://xeno-canto.org/1/%2e%2e/2",
  ])("rejects raw traversal before URL normalization: %s", async (sourceUrl) => {
    const traversal = structuredClone(detail);
    traversal.recommendations[0].call.recording_id = "2";
    traversal.recommendations[0].call.source_url = sourceUrl;
    traversal.recommendations[0].call.audio_url = "https://xeno-canto.org/2/download";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [traversal.plan] })
        : response(traversal),
    );

    render(<App />);
    await screen.findByRole("heading", { name: "Mexican Jay" });
    expect(screen.queryByText("Recordist: Ada Birder")).not.toBeInTheDocument();
    expect(document.querySelector("audio")).not.toBeInTheDocument();
    expect(screen.getAllByText("No licensed call example is available.").length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "View call source on Xeno-canto" })).not.toBeInTheDocument();
    const card = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"]');
    expect(within(card!).getByText("Call metadata did not match this recommendation.")).toBeVisible();
  });

  it("retains attribution for missing audio and a safe source after runtime failure", async () => {
    const missing = structuredClone(detail);
    missing.recommendations[0].call.audio_url = null;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [missing.plan] }) : response(missing),
    );
    const { unmount } = render(<App />);
    expect(await screen.findByText("Recordist: Ada Birder")).toBeVisible();
    expect(screen.getAllByText("No licensed call example is available.")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "View call source on Xeno-canto" })).toHaveAttribute(
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
    expect(await screen.findByText("Call playback failed.")).toBeVisible();
    expect(screen.getByText("Recordist: Ada Birder")).toBeVisible();
    expect(screen.getByRole("link", { name: "View call source on Xeno-canto" })).toBeVisible();
  });

  it("retains photo attribution and safe links after an image load failure", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [detail.plan] }) : response(detail),
    );
    render(<App />);
    const image = await screen.findByRole("img", {
      name: "Mexican Jay (Aphelocoma wollweberi)",
    });
    fireEvent.error(image);
    expect(await screen.findByText("Photo could not be loaded.")).toBeVisible();
    expect(screen.getByText("Creator: Pat Photographer")).toBeVisible();
    expect(screen.getByText("Rights holder: Arizona Bird Archive")).toBeVisible();
    expect(screen.getByText("Publisher: GBIF Fixture Publisher")).toBeVisible();
    expect(screen.getByRole("link", { name: "View photo source on GBIF" })).toBeVisible();
  });

  it.each([
    ["https://api.gbif.org/v1/occurrence/search", availablePhoto.source_url],
    [`${availablePhoto.display_url}?raw=true`, availablePhoto.source_url],
    [(availablePhoto.display_url || "").replace("occurrence/5938231789", "occurrence/1"), availablePhoto.source_url],
    [availablePhoto.display_url, "https://www.gbif.org/occurrence/1"],
    ["javascript:alert(1)", "javascript:alert(2)"],
  ])("fails unsafe photo display/source URLs closed without hiding attribution", async (displayUrl, sourceUrl) => {
    const unsafe = structuredClone(detail);
    unsafe.recommendations[0].photo.display_url = displayUrl;
    unsafe.recommendations[0].photo.source_url = sourceUrl;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [unsafe.plan] }) : response(unsafe),
    );
    render(<App />);
    expect(await screen.findByText("Creator: Pat Photographer")).toBeVisible();
    const card = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"]');
    expect(card).not.toBeNull();
    const photoArea = card!.querySelector<HTMLElement>(".recommendation-photo");
    expect(photoArea).not.toBeNull();
    expect(within(photoArea!).queryByRole("img")).not.toBeInTheDocument();
    expect(within(photoArea!).getByText("No licensed photo is available.")).toBeVisible();
    expect(within(photoArea!).getByText(/License:/)).toHaveTextContent("CC BY 4.0");
  });

  it("attaches media only from each recommendation object and labels global fallback", async () => {
    const attached = structuredClone(detail);
    attached.recommendations[0].call = unavailableCall;
    attached.recommendations[1].call = {
      ...availableCall,
      source_record_id: "2",
      recording_id: "2",
      species_name: "Buteo albonotatus",
      geographic_scope: "Global example",
      source_url: "https://xeno-canto.org/2",
      audio_url: "https://xeno-canto.org/2/download",
    };
    attached.media[0].recommendation_id = "rec-1";
    attached.media[0].audio_url = "https://xeno-canto.org/999/download";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [attached.plan] }) : response(attached),
    );
    render(<App />);
    await screen.findByRole("heading", { name: "Zone-tailed Hawk" });
    const first = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"]');
    const second = document.querySelector<HTMLElement>('[data-recommendation-id="rec-2"]');
    expect(first).not.toBeNull();
    expect(second).not.toBeNull();
    expect(first!.querySelector("audio")).not.toBeInTheDocument();
    expect(within(first!).getByText("No licensed call example is available.")).toBeVisible();
    const player = within(second!).getByLabelText("Play Zone-tailed Hawk · call · Quality A");
    expect(player).toHaveAttribute("src", "https://xeno-canto.org/2/download");
    expect(player).toHaveAttribute("controls");
    expect(player).toHaveAttribute("preload", "none");
    expect(player).not.toHaveAttribute("autoplay");
    expect(within(second!).getByText("Global example")).toBeVisible();
  });

  it.each([
    ["null photo", "photo", null, false, true],
    ["missing photo", "photo", undefined, false, true],
    ["nonobject photo", "photo", "invalid", false, true],
    ["wrong photo fields", "photo", { status: "available", caveats: [] }, false, true],
    ["malformed photo caveats", "photo", { ...availablePhoto, caveats: "invalid" }, false, true],
    ["null call", "call", null, true, false],
    ["missing call", "call", undefined, true, false],
    ["array call", "call", [], true, false],
    ["wrong call fields", "call", { status: "available", caveats: [] }, true, false],
    ["malformed call caveats", "call", { ...availableCall, caveats: [1] }, true, false],
  ])("fails %s independently without throwing", async (_, medium, value, photoActive, callActive) => {
    const adversarial = structuredClone(detail);
    Object.assign(adversarial.recommendations[0], { [medium]: value });
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [adversarial.plan] })
        : response(adversarial),
    );
    render(<App />);
    await screen.findByRole("heading", { name: "Mexican Jay" });
    const card = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"]');
    expect(card).not.toBeNull();
    expect(Boolean(within(card!).queryByRole("img"))).toBe(photoActive);
    expect(Boolean(card!.querySelector("audio"))).toBe(callActive);
    expect(within(card!).getByRole("heading", { name: "Mexican Jay" })).toBeVisible();
  });

  it("rejects different-species and conflicting source identities without misleading labels", async () => {
    const adversarial = structuredClone(detail);
    adversarial.recommendations[0].photo.species_name = "Buteo albonotatus";
    adversarial.recommendations[0].call.species_name = "Buteo albonotatus";
    adversarial.recommendations[0].call.source_record_id = "XC2";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans"
        ? response({ plans: [adversarial.plan] })
        : response(adversarial),
    );
    render(<App />);
    await screen.findByRole("heading", { name: "Mexican Jay" });
    const card = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"]');
    expect(card).not.toBeNull();
    expect(within(card!).queryByRole("img")).not.toBeInTheDocument();
    expect(card!.querySelector("audio")).not.toBeInTheDocument();
    expect(within(card!).getByText("No licensed photo is available.")).toBeVisible();
    expect(within(card!).getByText("No licensed call example is available.")).toBeVisible();
    expect(within(card!).getByText("Photo metadata did not match this recommendation.")).toBeVisible();
    expect(within(card!).getByText("Call metadata did not match this recommendation.")).toBeVisible();
    for (const hidden of [
      "Creator: Pat Photographer",
      "Rights holder: Arizona Bird Archive",
      "Publisher: GBIF Fixture Publisher",
      "Arizona recording",
      "Type: call",
      "Quality: A",
      "Recordist: Ada Birder",
    ]) expect(within(card!).queryByText(hidden)).not.toBeInTheDocument();
    expect(within(card!).queryByText(/License:/)).not.toBeInTheDocument();
    expect(within(card!).queryByRole("link", { name: "View photo source on GBIF" })).not.toBeInTheDocument();
    expect(within(card!).queryByRole("link", { name: "View call source on Xeno-canto" })).not.toBeInTheDocument();
    expect(within(card!).queryByLabelText(/Play Mexican Jay/)).not.toBeInTheDocument();
    expect(within(card!).queryByAltText(/Mexican Jay/)).not.toBeInTheDocument();
  });

  it("suppresses all call semantics for a cross-ID recording while preserving the photo", async () => {
    const crossId = structuredClone(detail);
    crossId.recommendations[0].call.source_record_id = "XC2";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [crossId.plan] }) : response(crossId),
    );
    render(<App />);
    expect(await screen.findByRole("img", {
      name: "Mexican Jay (Aphelocoma wollweberi)",
    })).toBeVisible();
    const card = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"]');
    const callArea = card!.querySelector<HTMLElement>(".recommendation-call");
    expect(callArea).not.toBeNull();
    expect(within(callArea!).getByText("No licensed call example is available.")).toBeVisible();
    expect(within(callArea!).getByText("Call metadata did not match this recommendation.")).toBeVisible();
    for (const hidden of [
      "Arizona recording",
      "Type: call",
      "Quality: A",
      "Recordist: Ada Birder",
    ]) expect(within(callArea!).queryByText(hidden)).not.toBeInTheDocument();
    expect(within(callArea!).queryByText(/License:/)).not.toBeInTheDocument();
    expect(within(callArea!).queryByRole("link")).not.toBeInTheDocument();
    expect(card!.querySelector("audio")).not.toBeInTheDocument();
    expect(within(card!).getByText("Creator: Pat Photographer")).toBeVisible();
  });

  it("accepts canonical XC source IDs and authority-free species normalization", async () => {
    const normalized = structuredClone(detail);
    normalized.recommendations[0].photo.species_name = "Aphelocoma wollweberi Kaup, 1854";
    normalized.recommendations[0].call.species_name = "Aphelocoma wollweberi (Kaup, 1854)";
    normalized.recommendations[0].call.source_record_id = "XC1";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [normalized.plan] }) : response(normalized),
    );
    render(<App />);
    expect(await screen.findByRole("img", {
      name: "Mexican Jay (Aphelocoma wollweberi)",
    })).toBeVisible();
    expect(document.querySelector("audio")).toHaveAttribute(
      "src", "https://xeno-canto.org/1/download",
    );
  });

  it("uses exact common-name identity only when the owning scientific name is absent", async () => {
    const fallback = structuredClone(detail);
    fallback.recommendations[0].scientific_name = null;
    fallback.recommendations[0].photo.species_name = "Mexican Jay";
    fallback.recommendations[0].call.species_name = "Mexican Jay";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [fallback.plan] }) : response(fallback),
    );
    const { unmount } = render(<App />);
    expect(await screen.findByRole("img", { name: "Mexican Jay" })).toBeVisible();
    expect(document.querySelector("audio")).toBeInTheDocument();
    unmount();

    fallback.recommendations[0].photo.species_name = "mexican jay";
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [fallback.plan] }) : response(fallback),
    );
    render(<App />);
    await screen.findByRole("heading", { name: "Mexican Jay" });
    const card = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"]');
    expect(within(card!).queryByRole("img")).not.toBeInTheDocument();
    expect(card!.querySelector("audio")).toBeInTheDocument();
  });

  it("requires license label/url consistency and supports canonical CC0", async () => {
    const rejected = structuredClone(detail);
    rejected.recommendations[0].photo.license_text = null;
    rejected.recommendations[0].call.license_text = "CC BY-NC 4.0";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [rejected.plan] }) : response(rejected),
    );
    const { unmount } = render(<App />);
    await screen.findByRole("heading", { name: "Mexican Jay" });
    const rejectedCard = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"]');
    expect(within(rejectedCard!).queryByRole("img")).not.toBeInTheDocument();
    expect(rejectedCard!.querySelector("audio")).not.toBeInTheDocument();
    expect(within(rejectedCard!).getAllByText("License: unavailable")).toHaveLength(2);
    expect(within(rejectedCard!).queryByText("CC BY-NC 4.0")).not.toBeInTheDocument();
    expect(within(rejectedCard!).getByText("Creator: Pat Photographer")).toBeVisible();
    expect(within(rejectedCard!).getByText("Recordist: Ada Birder")).toBeVisible();
    unmount();

    const cc0 = structuredClone(detail);
    cc0.recommendations[0].photo.license_text = "CC0 1.0";
    cc0.recommendations[0].photo.license_url = "https://creativecommons.org/publicdomain/zero/1.0/";
    cc0.recommendations[0].call.license_text = "CC0 1.0";
    cc0.recommendations[0].call.license_url = "https://creativecommons.org/publicdomain/zero/1.0/";
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [cc0.plan] }) : response(cc0),
    );
    render(<App />);
    expect(await screen.findByRole("img", {
      name: "Mexican Jay (Aphelocoma wollweberi)",
    })).toBeVisible();
    expect(document.querySelector("audio")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "CC0 1.0" })).toHaveLength(2);
  });

  it("contains long unbroken media metadata within narrow grid children", async () => {
    const long = "Attribution".repeat(80);
    const narrow = structuredClone(detail);
    narrow.recommendations[0].photo.creator = long;
    narrow.recommendations[0].photo.rights_holder = long;
    narrow.recommendations[0].photo.publisher = long;
    narrow.recommendations[0].call.recordist = long;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [narrow.plan] }) : response(narrow),
    );
    render(<App />);
    await screen.findByText(`Creator: ${long}`);
    const card = document.querySelector<HTMLElement>('[data-recommendation-id="rec-1"]');
    const metadata = card!.querySelector<HTMLElement>(".media-metadata");
    expect(card).not.toBeNull();
    expect(metadata).not.toBeNull();
    expect(getComputedStyle(card!).minWidth).toBe("0");
    expect(getComputedStyle(metadata!).minWidth).toBe("0");
    expect(getComputedStyle(metadata!).overflowWrap).toBe("anywhere");
    expect(getComputedStyle(metadata!).wordBreak).toBe("break-word");
    expect(card!.closest(".species-grid")).not.toBeNull();
  });

  it.each([
    [0, 0],
    [3, 3],
    [4, 4],
  ])("renders %s recommendation cards without an unnecessary pager", async (count, expected) => {
    const compact = paginatedDetail("boundary", count, 0, 0);
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [compact.plan] }) : response(compact),
    );
    render(<App />);
    const heading = await screen.findByRole("heading", { name: "High-likelihood Species" });
    const group = heading.closest("section");
    expect(group).not.toBeNull();
    expect(group!.querySelectorAll(".species-card")).toHaveLength(expected);
    expect(within(group!).queryByRole("navigation")).not.toBeInTheDocument();
    if (count === 0) expect(within(group!).getByText("No supported targets in this group.")).toBeVisible();
  });

  it("paginates recommendation groups independently with global ranks and plan reset", async () => {
    const user = userEvent.setup();
    const first = paginatedDetail("plan-a", 6, 5, 1);
    const second = paginatedDetail("plan-b", 6, 5, 1);
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/trip-plans") return response({ plans: [first.plan, second.plan] });
      return response(url.endsWith("plan-b") ? second : first);
    });
    render(<App />);
    await screen.findByRole("heading", { name: "Plan plan-a" });
    const high = screen.getByRole("heading", { name: "High-likelihood Species" }).closest("section")!;
    const uncommon = screen.getByRole("heading", { name: "Uncommon but Plausible Targets" }).closest("section")!;
    expect(high.querySelectorAll(".species-card")).toHaveLength(4);
    expect(uncommon.querySelectorAll(".species-card")).toHaveLength(4);
    expect(within(high).getByText("Showing 1–4 of 6")).toBeVisible();
    expect(within(uncommon).getByText("Showing 1–4 of 5")).toBeVisible();
    expect(within(high).getByRole("button", { name: "Previous High-likelihood Species page" })).toBeDisabled();
    expect(within(high).getByRole("button", { name: "Next High-likelihood Species page" })).toBeEnabled();
    expect(getComputedStyle(high.querySelector(".species-grid")!).gridTemplateColumns).toContain("repeat(4");

    await user.click(within(high).getByRole("button", { name: "Next High-likelihood Species page" }));
    expect(within(high).getByText("High Bird 5")).toBeVisible();
    expect(within(high).getByText("#5")).toBeVisible();
    expect(within(high).getByText("#6")).toBeVisible();
    expect(within(high).getByText("Showing 5–6 of 6")).toBeVisible();
    expect(within(high).getByRole("button", { name: "Next High-likelihood Species page" })).toBeDisabled();
    expect(within(uncommon).getByText("Uncommon Bird 1")).toBeVisible();

    await user.click(within(uncommon).getByRole("button", { name: "Next Uncommon but Plausible Targets page" }));
    expect(within(uncommon).getByText("Uncommon Bird 5")).toBeVisible();
    expect(within(uncommon).getByText("#105")).toBeVisible();
    expect(within(high).getByText("High Bird 5")).toBeVisible();

    await user.selectOptions(screen.getByLabelText("Previous plans"), "plan-b");
    await screen.findByRole("heading", { name: "Plan plan-b" });
    const resetHigh = screen.getByRole("heading", { name: "High-likelihood Species" }).closest("section")!;
    const resetUncommon = screen.getByRole("heading", { name: "Uncommon but Plausible Targets" }).closest("section")!;
    expect(within(resetHigh).getByText("High Bird 1")).toBeVisible();
    expect(within(resetHigh).queryByText("High Bird 5")).not.toBeInTheDocument();
    expect(within(resetUncommon).getByText("Uncommon Bird 1")).toBeVisible();
    expect(within(resetHigh).getByRole("button", { name: "Previous High-likelihood Species page" })).toBeDisabled();
    expect(within(resetUncommon).getByRole("button", { name: "Previous Uncommon but Plausible Targets page" })).toBeDisabled();
  });

  it.each([
    [0, 0, "Showing 0 of 0"],
    [7, 7, "Showing 1–7 of 7"],
    [20, 20, "Showing 1–20 of 20"],
  ])("keeps evidence collapsed and bounds a %s-row first page", async (count, visible, range) => {
    const compact = paginatedDetail("evidence-boundary", 1, 1, count);
    vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input) === "/api/trip-plans" ? response({ plans: [compact.plan] }) : response(compact),
    );
    render(<App />);
    await screen.findByRole("heading", { name: "Plan evidence-boundary" });
    const summary = screen.getByText("Evidence and Provenance").closest("summary")!;
    const disclosure = summary.closest("details")!;
    expect(disclosure).not.toHaveAttribute("open");
    expect(within(disclosure).getByText("Agent Workflow").closest("details")).not.toHaveAttribute("open");
    await userEvent.click(summary);
    expect(disclosure).toHaveAttribute("open");
    expect(disclosure.querySelectorAll("tbody tr")).toHaveLength(visible);
    expect(within(disclosure).getByText(range)).toBeVisible();
    expect(within(disclosure).getByRole("button", { name: "Previous evidence page" })).toBeDisabled();
    expect(within(disclosure).getByRole("button", { name: "Next evidence page" })).toBeDisabled();
    const size = within(disclosure).getByRole("combobox", { name: "Evidence rows per page" });
    expect(Array.from((size as HTMLSelectElement).options).map((option) => option.value)).toEqual(["20", "50", "100"]);
    expect(size).toHaveValue("20");
  });

  it("paginates evidence at exact boundaries and resets on size and plan changes", async () => {
    const user = userEvent.setup();
    const first = paginatedDetail("evidence-a", 1, 1, 105);
    const second = paginatedDetail("evidence-b", 1, 1, 60);
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/trip-plans") return response({ plans: [first.plan, second.plan] });
      return response(url.endsWith("evidence-b") ? second : first);
    });
    render(<App />);
    await screen.findByRole("heading", { name: "Plan evidence-a" });
    let disclosure = screen.getByText("Evidence and Provenance").closest("details")!;
    await user.click(within(disclosure).getByText("Evidence and Provenance"));
    const next = within(disclosure).getByRole("button", { name: "Next evidence page" });
    for (let page = 0; page < 5; page += 1) await user.click(next);
    expect(within(disclosure).getByText("Showing 101–105 of 105")).toBeVisible();
    expect(next).toBeDisabled();
    expect(within(disclosure).getByRole("button", { name: "Previous evidence page" })).toBeEnabled();
    expect(disclosure.querySelectorAll("tbody tr")).toHaveLength(5);

    const size = within(disclosure).getByRole("combobox", { name: "Evidence rows per page" });
    await user.selectOptions(size, "50");
    expect(within(disclosure).getByText("Showing 1–50 of 105")).toBeVisible();
    expect(within(disclosure).getByRole("button", { name: "Previous evidence page" })).toBeDisabled();
    await user.selectOptions(size, "100");
    expect(within(disclosure).getByText("Showing 1–100 of 105")).toBeVisible();
    await user.click(within(disclosure).getByRole("button", { name: "Next evidence page" }));
    expect(within(disclosure).getByText("Showing 101–105 of 105")).toBeVisible();

    await user.selectOptions(screen.getByLabelText("Previous plans"), "evidence-b");
    await screen.findByRole("heading", { name: "Plan evidence-b" });
    disclosure = screen.getByText("Evidence and Provenance").closest("details")!;
    expect(disclosure).not.toHaveAttribute("open");
    await user.click(within(disclosure).getByText("Evidence and Provenance"));
    expect(within(disclosure).getByText("Showing 1–20 of 60")).toBeVisible();
    expect(within(disclosure).getByRole("combobox", { name: "Evidence rows per page" })).toHaveValue("20");
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
