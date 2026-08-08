import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { EncounterPhotoLinks, EncounterThumbnail, TripEvidenceMap } from "./FieldMap";
import styles from "./styles.css?raw";
import type { CatalogPhoto, Evidence, MapSnapshot, TripPlanDetail } from "./types";

type FakeMapEvent = { features?: unknown[]; sourceId?: string; isSourceLoaded?: boolean };

const mapState = vi.hoisted(() => ({ maps: [] as Array<{
  options: Record<string, unknown>;
  handlers: Map<string, (event: FakeMapEvent) => void>;
  setData: ReturnType<typeof vi.fn>;
  fitBounds: ReturnType<typeof vi.fn>;
  setFilter: ReturnType<typeof vi.fn>;
  easeTo: ReturnType<typeof vi.fn>;
  resize: ReturnType<typeof vi.fn>;
  remove: ReturnType<typeof vi.fn>;
  clusterZoom: ReturnType<typeof vi.fn>;
  projectScale: number;
  features: unknown[];
}>, markers: [] as HTMLElement[], runtimeFailure: false, remoteBasemap: false }));

vi.mock("./openFreeMapStyle", () => ({
  loadOpenFreeMapStyle: () => Promise.resolve(mapState.remoteBasemap ? {
    status: "ready",
    style: {
      version: 8,
      sources: { openmaptiles: { type: "vector", url: "https://tiles.openfreemap.org/planet" } },
      glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
      layers: [{ id: "basemap-background", type: "background" }],
    },
  } : { status: "fallback" }),
}));

vi.mock("./maplibreRuntime", () => {
  class FakeMap {
    options: Record<string, unknown>;
    handlers = new Map<string, (event: FakeMapEvent) => void>();
    setData = vi.fn();
    fitBounds = vi.fn();
    setFilter = vi.fn();
    easeTo = vi.fn();
    resize = vi.fn();
    remove = vi.fn();
    clusterZoom = vi.fn().mockResolvedValue(8);
    projectScale = 200;
    features: unknown[] = [];
    constructor(options: Record<string, unknown>) { this.options = options; mapState.maps.push(this); }
    addControl() { return this; }
    getSource() { return { setData: this.setData, getClusterExpansionZoom: this.clusterZoom }; }
    getZoom() { return 5; }
    project(coordinates: [number, number]) {
      return { x: (coordinates[0] + 113) * this.projectScale, y: (coordinates[1] - 34) * this.projectScale };
    }
    querySourceFeatures() { return this.features; }
    queryRenderedFeatures() { return this.features; }
    on(event: string, layerOrHandler: string | ((event: FakeMapEvent) => void), handler?: (event: FakeMapEvent) => void) {
      this.handlers.set(handler ? `${event}:${layerOrHandler}` : event, handler ?? layerOrHandler as (event: FakeMapEvent) => void);
      return this;
    }
  }
  class FakeMarker {
    element: HTMLElement;
    constructor(options: { element: HTMLElement }) { this.element = options.element; mapState.markers.push(this.element); }
    setLngLat() { return this; }
    addTo() { document.body.append(this.element); return this; }
    remove() { this.element.remove(); return this; }
  }
  const runtime = { Map: FakeMap, Marker: FakeMarker, NavigationControl: class {} };
  return {
    loadMapLibre: () => mapState.runtimeFailure
      ? Promise.reject(new Error("runtime unavailable"))
      : Promise.resolve(runtime),
  };
});

function response(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

function snapshot(): MapSnapshot {
  const base = {
    scientific_name: "Avis fixture", family_scientific_name: "Fixtureidae",
    observation_count: 2, notable: false, latitude: 34.5, longitude: -112.4,
    access_warning: false,
  };
  return {
    snapshot_latest_observation_at: "2026-07-11T11:00:00",
    source_freshness_at: "2026-07-11T11:30:00",
    encounters: [
      { ...base, source_observation_id: "S1", species_code: "alpha2", common_name: "Alpha 2", family_common_name: "Zebra Family", observation_at: "2026-07-11T11:00:00", location_id: "L1", location_name: "Public One" },
      { ...base, source_observation_id: "S2", species_code: "alpha10", common_name: "alpha 10", family_common_name: "Alpha Family", observation_at: "2026-07-08T10:00:00", location_id: "L2", location_name: "Public Two", notable: true },
      { ...base, source_observation_id: "S3", species_code: "beta", common_name: "Beta", family_common_name: "Alpha Family", observation_at: "2026-06-22T10:00:00", location_id: "L3", location_name: "Trail (private)", access_warning: true },
      { ...base, source_observation_id: "S4", species_code: "fallback", common_name: null, scientific_name: "Gamma scientific", family_common_name: null, observation_at: "2026-07-10T08:00:00", location_id: "L4", location_name: "Public Four" },
    ],
    photos: ["alpha2", "alpha10", "beta", "fallback"].map((species_code) => ({
      species_code,
      scientific_name: species_code === "fallback" ? "Gamma scientific" : "Avis fixture",
      photo: { status: "unavailable" as const, source_record_id: null, species_name: null, display_url: null, source_url: null, creator: null, rights_holder: null, publisher: null, format: null, license_text: null, license_url: null, selection_reason: null, provider: null, license_code: null, original_width: null, original_height: null, caveats: [], lookup_at: null },
    })),
  };
}

function snapshotWithRepeatedSpecies(): MapSnapshot {
  const value = snapshot();
  const alpha = value.encounters[0];
  value.encounters = [
    {
      ...alpha,
      source_observation_id: "S1-oldest",
      observation_at: "2026-07-01T07:00:00",
      observation_count: 1,
      location_id: "L1-oldest",
      location_name: "Public Oldest",
      latitude: 32.1,
      longitude: -110.9,
    },
    ...value.encounters,
    {
      ...alpha,
      source_observation_id: "S1-middle",
      observation_at: "2026-07-10T09:00:00",
      observation_count: 4,
      location_id: "L1-middle",
      location_name: "Public Middle",
      latitude: 33.4,
      longitude: -111.7,
    },
  ];
  return value;
}

function snapshotWithPhoto(): MapSnapshot {
  const value = snapshot();
  value.photos[0].photo = {
    status: "available", source_record_id: "101", species_name: "Avis fixture",
    display_url: "https://inaturalist-open-data.s3.amazonaws.com/photos/101/large.jpg",
    source_url: "https://www.inaturalist.org/photos/101", creator: "Fixture Photographer",
    rights_holder: null, publisher: null, format: null, provider: "inaturalist",
    license_text: "CC BY 4.0", license_code: "CC BY 4.0",
    license_url: "https://creativecommons.org/licenses/by/4.0/",
    original_width: 1600, original_height: 1200,
    selection_reason: "Fixture", caveats: [], lookup_at: "2026-07-11T08:00:00Z",
  };
  return value;
}

function usfwsPhoto(): CatalogPhoto {
  const value = snapshotWithPhoto();
  return {
    ...value.photos[0].photo,
    source_record_id: "usfws-rufous-1",
    display_url: `https://rufous-data.loughondata.com/rufous-media/v1/objects/ab/${"ab" + "c".repeat(62)}.webp`,
    source_url: "https://www.fws.gov/media/rufous--hummingbird",
    creator: "USFWS Photographer",
    publisher: "U.S. Fish and Wildlife Service",
    format: "image/webp",
    provider: "usfws",
    license_text: "Public Domain",
    license_code: "Public Domain",
    license_url: "https://www.fws.gov/notices",
    original_width: 650,
    original_height: 488,
    selection_reason: "Validated USFWS public-release photo",
  };
}

function wikimediaPhoto(): CatalogPhoto {
  return {
    ...usfwsPhoto(),
    source_record_id: `wikimedia-${"1".repeat(24)}`,
    source_url: "https://commons.wikimedia.org/wiki/File:Arizona_bird.jpg",
    creator: "Commons Photographer",
    publisher: null,
    provider: "wikimedia",
    license_text: "CC BY 4.0",
    license_code: "CC BY 4.0",
    license_url: "https://creativecommons.org/licenses/by/4.0/",
    selection_reason: "Validated Wikimedia Commons public-release photo",
  };
}

function tripEvidence(
  evidenceId: string,
  source: "ebird" | "gbif",
  sourceRecordId: string | null,
  latitude: unknown,
  longitude: unknown,
  distanceKm: unknown,
  overrides: Partial<Evidence> = {},
): Evidence {
  const isEbird = source === "ebird";
  return {
    evidence_id: evidenceId,
    recommendation_id: null,
    source,
    source_table: isEbird ? "recent_observation_evidence" : "gbif_occurrence_evidence",
    source_record_id: sourceRecordId,
    evidence_type: isEbird ? "recent_observation" : "occurrence_context",
    status: "available",
    retrieved_at: null,
    summary: {
      common_name: isEbird ? "Mexican Jay" : "Zone-tailed Hawk",
      ...(isEbird ? { location_name: "Thumb Butte" } : { locality: "Prescott National Forest" }),
      distance_km: distanceKm,
    },
    payload: { latitude, longitude, distance_km: distanceKm },
    caveats: [],
    ...overrides,
  };
}

function tripDetail(): TripPlanDetail {
  const latitude = 34.54;
  const longitude = -112.47;
  const gbifDistance = 111.32 * 0.01 * Math.cos(latitude * Math.PI / 180);
  const radiusKm = 50;
  const boundaryLatitude = latitude + radiusKm / 111.32;
  return {
    plan: {
      trip_plan_id: "plan-map",
      requested_location: "Thumb Butte, Prescott, AZ",
      normalized_location_name: "Thumb Butte, Prescott, AZ",
      latitude,
      longitude,
      region_code: "US-AZ",
      timezone: "America/Phoenix",
      window_start: "2026-07-12T06:00:00-07:00",
      window_end: "2026-07-12T07:30:00-07:00",
      duration_minutes: 90,
      skill_level: "beginner",
      constraints_text: null,
      plan_status: "complete",
      field_plan_text: "Listen first.",
      caveats: [],
      created_at: "2026-07-11T12:00:00Z",
      updated_at: "2026-07-11T12:00:00Z",
    },
    recommendations: [],
    evidence: [
      tripEvidence("ev-ebird", "ebird", "S1", latitude + 0.01, longitude, 1.1132),
      tripEvidence("ev-gbif", "gbif", "G1", latitude, longitude + 0.01, gbifDistance),
      tripEvidence("ev-boundary", "gbif", "G2", boundaryLatitude, longitude, radiusKm, {
        summary: { common_name: "Pinyon Jay", locality: "Radius boundary", distance_km: radiusKm },
      }),
      tripEvidence("ev-duplicate", "ebird", "S1", latitude + 0.01, longitude, 1.1132),
      tripEvidence("ev-same-submission-other-species", "ebird", "S1", latitude + 0.01, longitude, 1.1132, {
        summary: { common_name: "Juniper Titmouse", location_name: "Thumb Butte", distance_km: 1.1132 },
      }),
      tripEvidence("ev-far", "ebird", "FAR", latitude + 0.56, longitude, 62.3392, {
        summary: { common_name: "Far Bird", location_name: "Outside radius", distance_km: 62.3392 },
      }),
      tripEvidence("ev-malformed", "ebird", "BAD", "34.55", longitude, 1.1132, {
        summary: { common_name: "Malformed Bird", location_name: "Bad coordinates", distance_km: 1.1132 },
      }),
      tripEvidence("ev-unavailable", "gbif", "OFF", latitude, longitude, 0, {
        status: "unavailable",
        summary: { common_name: "Unavailable Bird", locality: "Not available", distance_km: 0 },
      }),
      tripEvidence("ev-weather", "ebird", "WEATHER", latitude, longitude, 0, {
        evidence_type: "weather_elevation_context",
        summary: { common_name: "Wrong evidence type", location_name: "Not a core record", distance_km: 0 },
      }),
    ],
    weather: null,
    media: [],
    tool_traces: [
      {
        tool_trace_id: "trace-ebird",
        step_order: 2,
        tool_name: "lookup_recent_observation_evidence",
        tool_status: "ok",
        started_at: null,
        completed_at: null,
        input: {},
        output_summary: { enforced_radius_km: radiusKm },
        caveats: [],
      },
      {
        tool_trace_id: "trace-gbif",
        step_order: 3,
        tool_name: "lookup_gbif_occurrence_evidence",
        tool_status: "ok",
        started_at: null,
        completed_at: null,
        input: {},
        output_summary: { enforced_radius_km: radiusKm },
        caveats: [],
      },
    ],
    calendar_invite: {
      status: "not_created",
      sequence: null,
      outbox_id: null,
      allowed_actions: ["send"],
      can_retry: false,
      updated_at: null,
      acceptance_notice: null,
    },
  };
}

beforeEach(() => {
  window.history.replaceState(null, "", "/map");
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-07-11T12:00:00Z"));
  mapState.maps.length = 0; mapState.markers.length = 0; mapState.runtimeFailure = false; mapState.remoteBasemap = false;
  Object.defineProperty(window, "matchMedia", { configurable: true, value: vi.fn().mockReturnValue({ matches: false }) });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); window.history.replaceState(null, "", "/"); });

describe("Rufous Field Map", () => {
  it("renders direct local map, exact alphabetical filters, current-clock windows, and stale empty disclosure", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshot()));
    render(<App />);

    const heading = await screen.findByRole("heading", { name: "Field Map", level: 1 });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(document.title).toBe("Field Map · Rufous");
    expect(screen.getByRole("link", { name: "Field Map" })).toHaveAttribute("aria-current", "page");
    expect(fetchMock).toHaveBeenCalledWith("/api/map-snapshot", { headers: { "Content-Type": "application/json" } });
    const resultCount = await screen.findByText("4 eligible encounters");
    expect(resultCount).toHaveClass("map-result-count", "sr-only");
    expect(resultCount).toHaveAttribute("aria-live", "polite");
    expect(Array.from((screen.getByLabelText("Species") as HTMLSelectElement).options).map((option) => option.text)).toEqual([
      "All species", "Alpha 2", "alpha 10", "Beta", "Gamma scientific",
    ]);
    expect(Array.from((screen.getByLabelText("Family") as HTMLSelectElement).options).map((option) => option.text)).toEqual([
      "All families", "Alpha Family", "Fixtureidae", "Zebra Family",
    ]);
    expect(Array.from((screen.getByLabelText("Recency") as HTMLSelectElement).options).map((option) => option.text)).toEqual([
      "All snapshot", "Last 48 hours", "Last 7 days", "Last 30 days",
    ]);

    await userEvent.selectOptions(screen.getByLabelText("Recency"), "48h");
    expect(screen.getByText("2 eligible encounters")).toHaveClass("sr-only");
    await userEvent.selectOptions(screen.getByLabelText("Recency"), "7d");
    expect(screen.getByText("3 eligible encounters")).toHaveClass("sr-only");
    await userEvent.selectOptions(screen.getByLabelText("Recency"), "30d");
    expect(screen.getByText("4 eligible encounters")).toHaveClass("sr-only");
    await userEvent.selectOptions(screen.getByLabelText("Recency"), "48h");
    await userEvent.selectOptions(screen.getByLabelText("Family"), "Alpha Family");
    expect(screen.getByText(/No persisted encounters fall inside this current-clock window/)).toBeVisible();
    expect(screen.getByText(/choose All snapshot/)).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText("Recency"), "all");
    expect(screen.getByText("2 eligible encounters")).toHaveClass("sr-only");
    await userEvent.selectOptions(screen.getByLabelText("Species"), "alpha10");
    expect(screen.getByText("1 eligible encounter")).toHaveClass("sr-only");
    expect(screen.getByText(/Source freshness:/)).toBeVisible();
    expect(screen.getByText(/not endorsed or certified/)).toBeVisible();
    const layout = screen.getByRole("heading", { name: "Arizona encounter map" }).closest(".field-map-layout")!;
    expect(Array.from(layout.children).map((child) => child.tagName)).toEqual(["SECTION", "ASIDE"]);
    const rail = layout.querySelector(".field-map-rail")!;
    expect(Array.from(rail.querySelectorAll(":scope > section h2")).map((heading) => heading.textContent)).toEqual([
      "Selected encounter", "Accessible encounter list",
    ]);
    expect(styles).toMatch(/\.field-map-layout\s*\{[^}]*grid-template-columns:\s*minmax\(0, 3fr\) minmax\(280px, 2fr\)/s);
    expect(styles).toMatch(/\.field-map-main\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s);
    expect(styles).toMatch(/\.sr-only\s*\{[^}]*position:\s*absolute;[^}]*width:\s*1px;[^}]*height:\s*1px/s);
    expect(styles).toMatch(/\.field-map-rail\s*\{[^}]*display:\s*grid;[^}]*gap:\s*18px/s);
    expect(styles).toMatch(/--field-stage-height:\s*clamp\(360px, 50dvh, 520px\)/);
    expect(styles).toMatch(/\.map-canvas\s*\{[^}]*min-height:\s*var\(--field-stage-height\)/s);
    expect(styles).toMatch(/\.encounter-list\s*\{[^}]*max-height:\s*var\(--field-stage-height\);[^}]*overflow-y:\s*auto/s);
    expect(styles).toMatch(/@media \(min-width:\s*1101px\)[\s\S]*?\.field-map-main\s*\{[^}]*grid-template-columns:\s*minmax\(250px, \.55fr\) minmax\(0, 1\.45fr\)/);
    expect(styles).toMatch(/\.field-map-main > \.field-map-layout,[\s\S]*?grid-column:\s*1 \/ -1/);
    expect(styles).toMatch(/@media \(min-width:\s*821px\) and \(max-width:\s*1050px\)[\s\S]*?\.field-map-layout\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/);
    expect(styles).toMatch(/@media \(max-width:\s*820px\)[\s\S]*?\.field-map-layout[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/);
    expect(styles).toMatch(/@media \(max-width:\s*540px\)[\s\S]*?\.map-canvas\s*\{\s*min-height:\s*360px/);
    expect(styles).toMatch(/\.encounter-sighting-button span\s*\{[^}]*overflow-wrap:\s*break-word;\s*word-break:\s*normal/s);
    expect(styles).toMatch(/\.encounter-stack-row\.is-stacked\s*\{[^}]*grid-template-columns:\s*44px minmax\(0, 1fr\) 44px/s);
    expect(styles).toMatch(/\.encounter-carousel-arrow\s*\{[^}]*color:\s*var\(--teal-800\);[^}]*background:\s*transparent;[^}]*border:\s*0;[^}]*box-shadow:\s*none/s);
    expect(styles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(styles).toContain("@media (prefers-contrast: more), (forced-colors: active)");
  });

  it("keeps hover and focus previews independent without panning or selecting", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => String(input) === "/api/map-snapshot" ? response(snapshot()) : response({}));
    render(<App />);
    await screen.findByRole("heading", { name: "Accessible encounter list" });
    const map = mapState.maps[0];
    act(() => map.handlers.get("load")?.({}));
    const row = screen.getByRole("button", { name: /Beta/ });
    fireEvent.focus(row);
    fireEvent.mouseEnter(row);
    fireEvent.mouseLeave(row);
    await waitFor(() => expect(map.setData.mock.calls.at(-1)?.[0].features[0].properties.source_observation_id).toBe("S3"));
    expect(map.easeTo).not.toHaveBeenCalled();
    expect(row).toHaveAttribute("aria-pressed", "false");
    fireEvent.blur(row);
    await waitFor(() => expect(map.setData.mock.calls.at(-1)?.[0].features).toHaveLength(0));

    fireEvent.mouseEnter(row);
    fireEvent.focus(row);
    fireEvent.blur(row);
    await waitFor(() => expect(map.setData.mock.calls.at(-1)?.[0].features[0].properties.source_observation_id).toBe("S3"));
    fireEvent.mouseLeave(row);
    await waitFor(() => expect(map.setData.mock.calls.at(-1)?.[0].features).toHaveLength(0));
  });

  it("groups each species once and cycles its sightings newest-first", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshotWithRepeatedSpecies()));
    render(<App />);

    const listHeading = await screen.findByRole("heading", { name: "Accessible encounter list" });
    const listPanel = listHeading.closest("section")!;
    const list = within(listPanel).getByRole("list");
    expect(Array.from(list.children)).toHaveLength(4);
    expect(within(listPanel).getByText(
      "4 species represented by 6 encounters. Stacks start with the newest sighting.",
    )).toBeVisible();

    const groups = within(list).getAllByRole("article");
    expect(groups.map((group) => group.getAttribute("aria-label"))).toEqual([
      "Alpha 2, 3 encounters",
      "alpha 10, 1 encounter",
      "Beta, 1 encounter",
      "Gamma scientific, 1 encounter",
    ]);
    const alphaGroup = within(list).getByRole("article", { name: "Alpha 2, 3 encounters" });
    expect(within(alphaGroup).getByRole("button", { name: /Select Alpha 2 sighting 1 of 3: Public One/ })).toBeVisible();
    expect(within(alphaGroup).getByText("Sighting 1 of 3 · newest first")).toBeVisible();
    expect(within(alphaGroup).getByText("3 sightings")).toBeVisible();
    expect(within(alphaGroup).getAllByText("Alpha 2")).toHaveLength(1);
    expect(within(alphaGroup).getByRole("button", { name: "Previous Alpha 2 sighting" })).toHaveTextContent("<");
    expect(within(alphaGroup).getByRole("button", { name: "Next Alpha 2 sighting" })).toHaveTextContent(">");
    const betaGroup = within(list).getByRole("article", { name: "Beta, 1 encounter" });
    expect(within(betaGroup).queryByRole("group", { name: "Browse Beta sightings" })).not.toBeInTheDocument();

    await userEvent.click(within(alphaGroup).getByRole("button", { name: "Next Alpha 2 sighting" }));
    expect(within(alphaGroup).getByRole("button", { name: /Select Alpha 2 sighting 2 of 3: Public Middle/ })).toBeVisible();
    expect(within(alphaGroup).getByText("Sighting 2 of 3 · newest first")).toBeVisible();
    const selected = screen.getByRole("heading", { name: "Selected encounter" }).closest("section")!;
    expect(within(selected).getByText("Public Middle")).toBeVisible();

    await userEvent.click(within(alphaGroup).getByRole("button", { name: "Next Alpha 2 sighting" }));
    expect(within(alphaGroup).getByRole("button", { name: /Select Alpha 2 sighting 3 of 3: Public Oldest/ })).toBeVisible();
    await userEvent.click(within(alphaGroup).getByRole("button", { name: "Next Alpha 2 sighting" }));
    expect(within(alphaGroup).getByRole("button", { name: /Select Alpha 2 sighting 1 of 3: Public One/ })).toBeVisible();
    await userEvent.click(within(alphaGroup).getByRole("button", { name: "Previous Alpha 2 sighting" }));
    expect(within(alphaGroup).getByRole("button", { name: /Select Alpha 2 sighting 3 of 3: Public Oldest/ })).toBeVisible();
  });

  it("keeps carousel, map selection, selected details, and all occurrence points aligned", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshotWithRepeatedSpecies()));
    render(<App />);
    const listHeading = await screen.findByRole("heading", { name: "Accessible encounter list" });
    await waitFor(() => expect(mapState.maps).toHaveLength(1));
    const map = mapState.maps[0];
    act(() => map.handlers.get("load")?.({}));
    expect(map.setData.mock.lastCall?.[0].features).toHaveLength(6);

    act(() => map.handlers.get("click:encounter-points")?.({
      features: [{ properties: { source_observation_id: "S1-middle" } }],
    }));
    const listPanel = listHeading.closest("section")!;
    const alphaGroup = within(listPanel).getByRole("article", { name: "Alpha 2, 3 encounters" });
    const middleCard = within(alphaGroup).getByRole("button", { name: /Select Alpha 2 sighting 2 of 3: Public Middle/ });
    expect(middleCard).toHaveAttribute("aria-pressed", "true");
    expect(within(alphaGroup).getByText("Sighting 2 of 3 · newest first")).toBeVisible();
    const selected = screen.getByRole("heading", { name: "Selected encounter" }).closest("section")!;
    expect(within(selected).getByText("Public Middle")).toBeVisible();
    expect(map.easeTo).toHaveBeenLastCalledWith(expect.objectContaining({ center: [-111.7, 33.4], zoom: 11 }));
    await waitFor(() => expect(map.setFilter).toHaveBeenLastCalledWith(
      "selected-encounter",
      ["==", ["get", "source_observation_id"], "S1-middle"],
    ));

    await userEvent.click(within(alphaGroup).getByRole("button", { name: "Next Alpha 2 sighting" }));
    const oldestCard = within(alphaGroup).getByRole("button", { name: /Select Alpha 2 sighting 3 of 3: Public Oldest/ });
    expect(oldestCard).toHaveAttribute("aria-pressed", "true");
    expect(within(selected).getByText("Public Oldest")).toBeVisible();
    expect(map.easeTo).toHaveBeenLastCalledWith(expect.objectContaining({ center: [-110.9, 32.1], zoom: 11 }));
    await waitFor(() => expect(map.setFilter).toHaveBeenLastCalledWith(
      "selected-encounter",
      ["==", ["get", "source_observation_id"], "S1-oldest"],
    ));
  });

  it("preserves photo source, license, and attribution after thumbnail load failure", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshotWithPhoto()));
    render(<App />);
    const image = await screen.findByRole("img", { name: "Alpha 2" });
    expect(screen.getByText("Photo: Fixture Photographer · CC BY 4.0 · iNaturalist")).toBeVisible();
    expect(screen.getByRole("link", { name: "iNaturalist photo source" })).toHaveAttribute(
      "href", "https://www.inaturalist.org/photos/101",
    );
    expect(screen.getByRole("link", { name: "CC BY 4.0 license" })).toHaveAttribute(
      "href", "https://creativecommons.org/licenses/by/4.0/",
    );
    fireEvent.error(image);
    const encounter = image.closest("li");
    expect(encounter).not.toBeNull();
    expect(within(encounter!).getByRole("status")).toHaveTextContent(
      "Photo unavailable · Photo: Fixture Photographer · CC BY 4.0 · iNaturalist",
    );
    expect(screen.getByRole("link", { name: "iNaturalist photo source" })).toBeVisible();
    expect(screen.getByRole("link", { name: "CC BY 4.0 license" })).toBeVisible();
  });

  it("labels published USFWS encounter thumbnails and source links from the photo provider", async () => {
    const photo = usfwsPhoto();
    render(<><EncounterThumbnail photo={photo} name="Alpha 2" /><EncounterPhotoLinks photo={photo} /></>);
    expect(screen.getByRole("img", { name: "Alpha 2" })).toBeVisible();
    expect(screen.getByText("Photo: USFWS Photographer · Public Domain · USFWS")).toBeVisible();
    expect(screen.getByRole("link", { name: "USFWS photo source" })).toHaveAttribute(
      "href", "https://www.fws.gov/media/rufous--hummingbird",
    );
    expect(screen.getByRole("link", { name: "Public Domain license" })).toHaveAttribute(
      "href", "https://www.fws.gov/notices",
    );
  });

  it("labels published Wikimedia Commons encounter thumbnails and source links", () => {
    const photo = wikimediaPhoto();
    render(<><EncounterThumbnail photo={photo} name="Alpha 2" /><EncounterPhotoLinks photo={photo} /></>);
    expect(screen.getByText("Photo: Commons Photographer · CC BY 4.0 · Wikimedia Commons")).toBeVisible();
    expect(screen.getByRole("link", { name: "Wikimedia Commons photo source" })).toHaveAttribute(
      "href",
      "https://commons.wikimedia.org/wiki/File:Arizona_bird.jpg",
    );
  });

  it("applies the latest filtered source only after load and keeps data, markers, count, and extent aligned", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshot()));
    render(<App />);
    await screen.findByText("4 eligible encounters");
    await waitFor(() => expect(mapState.maps).toHaveLength(1));
    const map = mapState.maps[0];
    expect(map.setData).not.toHaveBeenCalled();

    await userEvent.selectOptions(screen.getByLabelText("Species"), "alpha10");
    expect(screen.getByText("1 eligible encounter")).toHaveClass("sr-only");
    expect(map.setData).not.toHaveBeenCalled();
    act(() => map.handlers.get("load")?.({}));
    expect(map.setData).toHaveBeenCalledTimes(1);
    expect(map.setData.mock.calls[0][0].features.map((feature: { id: string }) => feature.id)).toEqual(["S2"]);
    expect(map.fitBounds).toHaveBeenLastCalledWith(
      [[-112.4, 34.5], [-112.4, 34.5]],
      expect.objectContaining({ padding: 50, maxZoom: 10 }),
    );

    map.features = [{ properties: { cluster_id: 2, point_count: 1 }, geometry: { type: "Point", coordinates: [-112.4, 34.5] } }];
    act(() => map.handlers.get("sourcedata")?.({ sourceId: "encounters", isSourceLoaded: true }));
    expect(screen.getByRole("button", { name: "Zoom to cluster containing 1 eligible encounter" })).toHaveTextContent("1");

    await userEvent.selectOptions(screen.getByLabelText("Species"), "all");
    expect(screen.getByText("4 eligible encounters")).toHaveClass("sr-only");
    expect(map.setData.mock.lastCall?.[0].features).toHaveLength(4);
    expect(screen.queryByRole("button", { name: "Zoom to cluster containing 1 eligible encounter" })).not.toBeInTheDocument();
    act(() => map.handlers.get("moveend")?.({}));
    expect(screen.queryByRole("button", { name: /Zoom to cluster/ })).not.toBeInTheDocument();
    map.features = [{ properties: { cluster_id: 4, point_count: 4 }, geometry: { type: "Point", coordinates: [-112.4, 34.5] } }];
    act(() => map.handlers.get("sourcedata")?.({ sourceId: "encounters", isSourceLoaded: true }));
    expect(screen.getByRole("button", { name: "Zoom to cluster containing 4 eligible encounters" })).toBeVisible();
    expect(map.fitBounds).toHaveBeenLastCalledWith(
      [[-114.82, 31.3], [-109, 37.1]],
      expect.objectContaining({ padding: 20 }),
    );

    await userEvent.selectOptions(screen.getByLabelText("Recency"), "48h");
    expect(screen.getByText("2 eligible encounters")).toHaveClass("sr-only");
    expect(map.setData.mock.lastCall?.[0].features).toHaveLength(2);
    act(() => map.handlers.get("moveend")?.({}));
    expect(screen.queryByRole("button", { name: /Zoom to cluster/ })).not.toBeInTheDocument();
    map.features = [{ properties: { cluster_id: 5, point_count: 2 }, geometry: { type: "Point", coordinates: [-112.4, 34.5] } }];
    act(() => map.handlers.get("sourcedata")?.({ sourceId: "encounters", isSourceLoaded: true }));
    expect(screen.getByRole("button", { name: "Zoom to cluster containing 2 eligible encounters" })).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText("Recency"), "all");
    expect(map.fitBounds).toHaveBeenLastCalledWith(
      [[-114.82, 31.3], [-109, 37.1]],
      expect.objectContaining({ padding: 20 }),
    );

    await userEvent.selectOptions(screen.getByLabelText("Family"), "Fixtureidae");
    expect(screen.getByText("1 eligible encounter")).toHaveClass("sr-only");
    expect(map.setData.mock.lastCall?.[0].features).toHaveLength(1);
    await userEvent.selectOptions(screen.getByLabelText("Species"), "alpha10");
    expect(screen.getByText("0 eligible encounters")).toHaveClass("sr-only");
    expect(map.setData.mock.lastCall?.[0].features).toHaveLength(0);
    expect(map.fitBounds).toHaveBeenLastCalledWith(
      [[-114.82, 31.3], [-109, 37.1]],
      expect.objectContaining({ padding: 20 }),
    );
    act(() => map.handlers.get("moveend")?.({}));
    expect(screen.queryByRole("button", { name: /Zoom to cluster/ })).not.toBeInTheDocument();
    map.features = [];
    act(() => map.handlers.get("sourcedata")?.({ sourceId: "encounters", isSourceLoaded: true }));
    expect(screen.queryByRole("button", { name: /Zoom to cluster/ })).not.toBeInTheDocument();
  });

  it("keeps list, point, cluster, selected card, warning, and profile navigation equivalent", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshot()));
    render(<App />);
    await screen.findByRole("heading", { name: "Accessible encounter list" });
    await waitFor(() => expect(mapState.maps).toHaveLength(1));
    const map = mapState.maps[0];
    const layers = (map.options.style as { layers: Array<{ id: string }> }).layers.map((layer) => layer.id);
    expect(layers.indexOf("selected-encounter")).toBeGreaterThan(layers.indexOf("encounter-points"));
    expect(layers.indexOf("selected-encounter")).toBeGreaterThan(layers.indexOf("preview-encounter"));
    act(() => map.handlers.get("load")?.({}));
    expect(map.setData).toHaveBeenCalledWith(expect.objectContaining({ features: expect.any(Array) }));
    expect(map.setData.mock.lastCall?.[0].features).toHaveLength(4);
    const betaButton = within(screen.getByRole("heading", { name: "Accessible encounter list" }).closest("section")!)
      .getByRole("button", { name: /Beta/ });
    vi.mocked(window.matchMedia).mockReturnValue({ matches: true } as MediaQueryList);
    await userEvent.click(betaButton);
    const selected = screen.getByRole("heading", { name: "Selected encounter" }).closest("section")!;
    expect(within(selected).getByRole("heading", { name: "Beta" })).toBeVisible();
    expect(within(selected).getByText(/Access may be restricted/)).toBeVisible();
    expect(betaButton).toHaveAttribute("aria-pressed", "true");
    expect(map.easeTo).toHaveBeenCalledWith(expect.objectContaining({ center: [-112.4, 34.5], zoom: 11, duration: 0 }));
    await waitFor(() => expect(map.setFilter).toHaveBeenLastCalledWith("selected-encounter", ["==", ["get", "source_observation_id"], "S3"]));
    await userEvent.selectOptions(screen.getByLabelText("Species"), "alpha10");
    expect(within(selected).getByText("Select a map point or encounter-list row for details.")).toBeVisible();
    await waitFor(() => expect(map.setFilter).toHaveBeenLastCalledWith("selected-encounter", ["==", ["get", "source_observation_id"], ""]));
    await userEvent.selectOptions(screen.getByLabelText("Species"), "all");

    act(() => map.handlers.get("click:encounter-points")?.({ features: [{ properties: { source_observation_id: "S2" } }] }));
    expect(await screen.findByRole("heading", { name: "alpha 10" })).toBeVisible();
    const alphaButton = within(screen.getByRole("heading", { name: "Accessible encounter list" }).closest("section")!)
      .getByRole("button", { name: /alpha 10/ });
    expect(alphaButton).toHaveAttribute("aria-pressed", "true");
    expect(map.easeTo).toHaveBeenLastCalledWith(expect.objectContaining({ center: [-112.4, 34.5], zoom: 11, duration: 0 }));
    await waitFor(() => expect(map.setFilter).toHaveBeenLastCalledWith("selected-encounter", ["==", ["get", "source_observation_id"], "S2"]));
    map.features = [{ properties: { cluster_id: 7, point_count: 23 }, geometry: { type: "Point", coordinates: [-111, 35] } }];
    map.handlers.get("sourcedata")?.({ sourceId: "encounters", isSourceLoaded: true });
    const clusterButton = await screen.findByRole("button", { name: "Zoom to cluster containing 23 eligible encounters" });
    expect(clusterButton).toHaveTextContent("23");
    await userEvent.click(clusterButton);
    await waitFor(() => expect(map.clusterZoom).toHaveBeenCalledWith(7));
    act(() => map.handlers.get("click:clusters")?.({ features: map.features }));
    await waitFor(() => expect(map.clusterZoom).toHaveBeenCalledTimes(2));
    expect(map.easeTo).toHaveBeenLastCalledWith(expect.objectContaining({ center: [-111, 35], zoom: 8, duration: 0 }));

    await userEvent.click(within(selected).getByRole("link", { name: "View bird profile" }));
    expect(window.location.pathname).toBe("/birds/alpha10");
  });

  it("uses only inline local style/geometry and cleans up on history navigation", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshot()));
    render(<App />);
    await screen.findByRole("heading", { name: "Arizona encounter map" });
    await waitFor(() => expect(mapState.maps).toHaveLength(1));
    const map = mapState.maps[0];
    const serialized = JSON.stringify(map.options.style);
    expect(serialized).not.toMatch(/https?:\/\//);
    expect(serialized).not.toContain("tiles");
    expect(serialized).not.toContain("glyphs");
    expect(serialized).not.toContain("sprite");
    expect(serialized).toContain("Apache County");

    window.history.pushState(null, "", "/");
    window.dispatchEvent(new PopStateEvent("popstate"));
    await waitFor(() => expect(map.remove).toHaveBeenCalled());
  });

  it("shows bounded loading and safe error states without constructing a map", async () => {
    let reject!: (reason: Error) => void;
    vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise((_resolve, rejectPromise) => { reject = rejectPromise; }));
    render(<App />);
    expect(await screen.findByText("Loading the local Field Map snapshot…")).toHaveAttribute("role", "status");
    reject(new Error("The local Field Map is unavailable"));
    expect(await screen.findByRole("alert")).toHaveTextContent("The local Field Map is unavailable");
    expect(mapState.maps).toHaveLength(0);
  });

  it("keeps filters and the accessible list available when the local renderer fails", async () => {
    mapState.runtimeFailure = true;
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshot()));
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The interactive map could not start. Filters and the accessible encounter list remain available.",
    );
    expect(screen.getByRole("heading", { name: "Accessible encounter list" })).toBeVisible();
    expect(screen.getByLabelText("Species")).toBeVisible();
    expect(mapState.maps).toHaveLength(0);
  });
});

describe("Rufous trip evidence map", () => {
  it("plots only distinct available core records inside the matching enforced radius", async () => {
    const detail = tripDetail();
    detail.recommendations = [
      { recommendation_group: "recently_reported", rank_order: 2, common_name: "Juniper Titmouse" },
      { recommendation_group: "gbif_context", rank_order: 3, common_name: "Zone-tailed Hawk" },
      { recommendation_group: "recently_reported", rank_order: 1, common_name: "Mexican Jay" },
    ] as TripPlanDetail["recommendations"];
    const { container, unmount } = render(<TripEvidenceMap detail={detail} />);

    expect(screen.getByRole("heading", { name: "Evidence Map" })).toBeVisible();
    expect(screen.getByText(
      "4 distinct persisted evidence records across 3 approximate mapped locations · 4 species · within the enforced 50 km radius",
    )).toBeVisible();
    const legend = screen.getByRole("list", { name: "Mapped evidence sources" });
    expect(within(legend).getByText("2 eBird reports · 1 location · 2 species")).toBeVisible();
    expect(within(legend).getByText("2 GBIF occurrences · 2 locations · 2 species")).toBeVisible();
    expect(within(legend).getByText("Trip location")).toBeVisible();
    expect(container.querySelector(".trip-map-recommendations")).toHaveTextContent(
      "Evidence-ranked recommendations: Mexican Jay · Juniper Titmouse",
    );
    expect(screen.getByText("Distinct recent eBird submissions; not encounter probability.")).toBeVisible();
    expect(screen.getByRole("region", { name: /4 distinct persisted evidence records across 3 approximate locations inside the enforced 50 kilometer radius/ })).toBeVisible();
    await waitFor(() => expect(mapState.maps).toHaveLength(1));

    const map = mapState.maps[0];
    const style = map.options.style as {
      sources: Record<string, { data: { features: Array<{ geometry: { coordinates: unknown }; properties: Record<string, unknown> }> } }>;
    };
    expect(style.sources["trip-evidence"].data.features).toHaveLength(3);
    expect(style.sources["trip-evidence"].data.features.map((feature) => feature.properties.source_mix)).toEqual([
      "gbif", "ebird", "gbif",
    ]);
    expect(style.sources["trip-evidence"].data.features.map((feature) => feature.properties.record_count)).toEqual([1, 2, 1]);
    const radiusRing = style.sources["trip-radius"].data.features[0].geometry.coordinates as [number, number][][];
    expect(radiusRing[0]).toHaveLength(65);
    expect(radiusRing[0][0]).toEqual(radiusRing[0].at(-1));
    expect(style.sources["trip-origin"].data.features[0].geometry.coordinates).toEqual([-112.47, 34.54]);
    expect(map.options.bounds).toEqual([
      [expect.any(Number), expect.any(Number)],
      [expect.any(Number), expect.any(Number)],
    ]);
    const serializedStyle = JSON.stringify(map.options.style);
    expect(serializedStyle).not.toMatch(/https?:\/\//);
    expect(serializedStyle).not.toContain("tiles");
    expect(serializedStyle).not.toContain("glyphs");
    expect(serializedStyle).not.toContain("sprite");
    expect(serializedStyle).toContain("Apache County");
    expect(await screen.findByText(/using the bundled Arizona boundary fallback/)).toBeVisible();

    act(() => map.handlers.get("load")?.({}));
    expect(map.resize).toHaveBeenCalledOnce();
    expect(map.fitBounds).toHaveBeenCalledWith(map.options.bounds, {
      padding: 32, maxZoom: 10, duration: 0,
    });
    await userEvent.click(screen.getByRole("button", { name: "Show full 50 km radius" }));
    expect(map.resize).toHaveBeenCalledTimes(2);
    expect(map.fitBounds).toHaveBeenCalledTimes(2);

    await userEvent.click(screen.getByText("Mapped evidence locations (3)"));
    const mappedLocations = screen.getByText("Mapped evidence locations (3)").closest("details")!;
    const thumbButte = within(mappedLocations).getByRole("button", { name: /Thumb Butte/ });
    expect(thumbButte).toHaveTextContent("2 eBird reports · 2 species · 1.1 km from the trip location");
    expect(thumbButte).toHaveTextContent("Juniper Titmouse (1) · Mexican Jay (1)");
    expect(within(mappedLocations).getByRole("button", { name: /Prescott National Forest/ })).toHaveTextContent(
      "1 GBIF occurrence · 1 species · 0.9 km from the trip location",
    );
    expect(within(mappedLocations).getByRole("button", { name: /Radius boundary/ })).toHaveTextContent(
      "1 GBIF occurrence · 1 species · 50.0 km from the trip location",
    );
    expect(screen.queryByText(/Far Bird|Malformed Bird|Unavailable Bird|Wrong evidence type/)).not.toBeInTheDocument();
    expect(screen.queryByText(/S1|G1|G2|FAR|BAD|OFF|WEATHER/)).not.toBeInTheDocument();
    expect(screen.getByText(/not predicted current presence/)).toBeVisible();
    expect(screen.getByText(/planner's displayed local-distance approximation/)).toBeVisible();
    expect(styles).toMatch(/\.trip-evidence-map \.map-canvas\s*\{[^}]*min-height:\s*clamp\(300px, 28vw, 360px\)/s);
    expect(styles).toMatch(/@media \(max-width:\s*540px\)[\s\S]*?\.trip-evidence-map \.map-canvas\s*\{\s*min-height:\s*260px/);

    const clusterMarker = screen.getByRole("button", {
      name: "Zoom to 2 approximate evidence locations containing 3 records",
    });
    expect(clusterMarker).toHaveTextContent("2 loc");
    await userEvent.click(clusterMarker);
    expect(map.fitBounds).toHaveBeenLastCalledWith([
      [-112.47, 34.54],
      [-112.46, 34.55],
    ], { padding: 72, maxZoom: 17, duration: 350 });

    map.projectScale = 10_000;
    act(() => map.handlers.get("moveend")?.({}));
    expect(clusterMarker).not.toBeInTheDocument();
    const locationMarker = await screen.findByRole("button", {
      name: /2 records across 2 species at Thumb Butte, 2 eBird reports, 1\.1 km from the trip location/,
    });
    expect(document.activeElement).toHaveClass("trip-map-marker");
    expect(document.activeElement).toHaveAccessibleName(/Prescott National Forest|Thumb Butte/);
    expect(locationMarker).toHaveTextContent("2");
    await userEvent.click(locationMarker);
    expect(locationMarker).toHaveAttribute("aria-pressed", "true");
    expect(thumbButte).toHaveAttribute("aria-pressed", "true");
    expect(map.easeTo).toHaveBeenLastCalledWith(expect.objectContaining({
      center: [-112.47, 34.55], zoom: 12, duration: 350,
    }));
    expect(screen.getAllByText("2 eBird reports · 2 species · 1.1 km from the trip location")).toHaveLength(2);
    act(() => map.handlers.get("moveend")?.({}));
    const refreshedLocationMarker = await screen.findByRole("button", {
      name: /2 records across 2 species at Thumb Butte, 2 eBird reports, 1\.1 km from the trip location/,
    });
    expect(refreshedLocationMarker).not.toBe(locationMarker);
    expect(refreshedLocationMarker).toHaveFocus();
    expect(refreshedLocationMarker).toHaveAttribute("aria-pressed", "true");

    unmount();
    expect(map.remove).toHaveBeenCalledOnce();
    expect(locationMarker).not.toBeInTheDocument();
    expect(clusterMarker).not.toBeInTheDocument();
  });

  it("uses the validated labeled basemap while retaining local evidence and Census overlays", async () => {
    mapState.remoteBasemap = true;
    render(<TripEvidenceMap detail={tripDetail()} />);

    await waitFor(() => expect(mapState.maps).toHaveLength(1));
    const serializedStyle = JSON.stringify(mapState.maps[0].options.style);
    expect(serializedStyle).toContain("https://tiles.openfreemap.org/planet");
    expect(serializedStyle).toContain("https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf");
    expect(serializedStyle).toContain("Apache County");
    expect(serializedStyle).toContain("trip-evidence");
    expect(screen.getByRole("link", { name: "OpenFreeMap" })).toHaveAttribute("href", "https://openfreemap.org/");
    expect(screen.getByRole("link", { name: "OpenMapTiles" })).toBeVisible();
    expect(screen.getByRole("link", { name: "OpenStreetMap contributors" })).toBeVisible();
    expect(screen.queryByText(/bundled Arizona boundary fallback/)).not.toBeInTheDocument();
  });

  it("explains why it cannot map evidence when successful lookup traces disagree", () => {
    const detail = tripDetail();
    detail.tool_traces[1].output_summary.enforced_radius_km = 49;
    render(<TripEvidenceMap detail={detail} />);

    expect(screen.getByText(/does not contain matching successful eBird and GBIF enforced-radius traces/)).toBeVisible();
    expect(screen.queryByRole("region", { name: /persisted evidence records/ })).not.toBeInTheDocument();
    expect(mapState.maps).toHaveLength(0);
  });

  it("keeps the enforced-radius context when no evidence has qualifying coordinates", async () => {
    const detail = tripDetail();
    detail.evidence = detail.evidence.filter((row) => row.evidence_id === "ev-far");
    render(<TripEvidenceMap detail={detail} />);

    expect(screen.getByText(
      "0 distinct persisted evidence records across 0 approximate mapped locations · 0 species · within the enforced 50 km radius",
    )).toBeVisible();
    expect(screen.getByRole("region", { name: /0 distinct persisted evidence records across 0 approximate locations inside the enforced 50 kilometer radius/ })).toBeVisible();
    await userEvent.click(screen.getByText("Mapped evidence locations (0)"));
    expect(screen.getByText("No qualifying coordinate-bearing evidence was persisted for this plan.")).toBeVisible();
    expect(mapState.maps).toHaveLength(1);
  });
});
