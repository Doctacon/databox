import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import styles from "./styles.css?raw";
import type { MapSnapshot } from "./types";

const mapState = vi.hoisted(() => ({ maps: [] as Array<{
  options: Record<string, unknown>;
  handlers: Map<string, (event: { features?: unknown[] }) => void>;
  setData: ReturnType<typeof vi.fn>;
  easeTo: ReturnType<typeof vi.fn>;
  remove: ReturnType<typeof vi.fn>;
  clusterZoom: ReturnType<typeof vi.fn>;
  features: unknown[];
}>, markers: [] as HTMLElement[] }));

vi.mock("maplibre-gl", () => {
  class FakeMap {
    options: Record<string, unknown>;
    handlers = new Map<string, (event: { features?: unknown[] }) => void>();
    setData = vi.fn();
    easeTo = vi.fn();
    remove = vi.fn();
    clusterZoom = vi.fn().mockResolvedValue(8);
    features: unknown[] = [];
    constructor(options: Record<string, unknown>) { this.options = options; mapState.maps.push(this); }
    addControl() { return this; }
    getSource() { return { setData: this.setData, getClusterExpansionZoom: this.clusterZoom }; }
    getZoom() { return 5; }
    querySourceFeatures() { return this.features; }
    on(event: string, layerOrHandler: string | ((event: { features?: unknown[] }) => void), handler?: (event: { features?: unknown[] }) => void) {
      this.handlers.set(handler ? `${event}:${layerOrHandler}` : event, handler ?? layerOrHandler as (event: { features?: unknown[] }) => void);
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
  return { default: { Map: FakeMap, Marker: FakeMarker, NavigationControl: class {} }, Map: FakeMap, Marker: FakeMarker, NavigationControl: class {} };
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
  };
}

beforeEach(() => {
  window.history.replaceState(null, "", "/map");
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-07-11T12:00:00Z"));
  mapState.maps.length = 0; mapState.markers.length = 0;
  Object.defineProperty(window, "matchMedia", { configurable: true, value: vi.fn().mockReturnValue({ matches: false }) });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); window.history.replaceState(null, "", "/"); });

describe("Rufous Field Map", () => {
  it("renders direct local map, exact alphabetical filters, current-clock windows, and stale empty disclosure", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshot()));
    render(<App />);

    const heading = await screen.findByRole("heading", { name: "Field Map", level: 1 });
    expect(heading).toHaveFocus();
    expect(document.title).toBe("Field Map · Rufous");
    expect(screen.getByRole("link", { name: "Field Map" })).toHaveAttribute("aria-current", "page");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/map-snapshot");
    expect(await screen.findByText("4 eligible encounters")).toBeVisible();
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
    expect(screen.getByText("2 eligible encounters")).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText("Recency"), "7d");
    expect(screen.getByText("3 eligible encounters")).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText("Recency"), "30d");
    expect(screen.getByText("4 eligible encounters")).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText("Recency"), "48h");
    await userEvent.selectOptions(screen.getByLabelText("Family"), "Alpha Family");
    expect(screen.getByText(/No persisted encounters fall inside this current-clock window/)).toBeVisible();
    expect(screen.getByText(/choose All snapshot/)).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText("Recency"), "all");
    expect(screen.getByText("2 eligible encounters")).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText("Species"), "alpha10");
    expect(screen.getByText("1 eligible encounter")).toBeVisible();
    expect(screen.getByText(/Source freshness:/)).toBeVisible();
    expect(screen.getByText(/not endorsed or certified/)).toBeVisible();
    expect(styles).toMatch(/\.field-map-layout\s*\{[^}]*grid-template-columns:\s*minmax\(0, 3fr\) minmax\(280px, 2fr\)/s);
    expect(styles).toMatch(/@media \(max-width:\s*820px\)[\s\S]*?\.field-map-layout\s*\{\s*grid-template-columns:\s*minmax\(0, 1fr\)/);
    expect(styles).toMatch(/@media \(max-width:\s*540px\)[\s\S]*?\.map-canvas\s*\{\s*min-height:\s*360px/);
    expect(styles).toMatch(/\.encounter-list button span\s*\{[^}]*overflow-wrap:\s*break-word;\s*word-break:\s*normal/s);
    expect(styles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(styles).toContain("@media (prefers-contrast: more), (forced-colors: active)");
  });

  it("keeps list, point, cluster, selected card, warning, and profile navigation equivalent", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshot()));
    render(<App />);
    await screen.findByRole("heading", { name: "Accessible encounter list" });
    await waitFor(() => expect(mapState.maps).toHaveLength(1));
    const map = mapState.maps[0];
    const betaButton = within(screen.getByRole("heading", { name: "Accessible encounter list" }).closest("section")!)
      .getByRole("button", { name: /Beta/ });
    vi.mocked(window.matchMedia).mockReturnValue({ matches: true } as MediaQueryList);
    await userEvent.click(betaButton);
    const selected = screen.getByRole("heading", { name: "Selected encounter" }).closest("section")!;
    expect(within(selected).getByRole("heading", { name: "Beta" })).toBeVisible();
    expect(within(selected).getByText(/Access may be restricted/)).toBeVisible();
    expect(betaButton).toHaveAttribute("aria-pressed", "true");
    expect(map.easeTo).toHaveBeenCalledWith(expect.objectContaining({ center: [-112.4, 34.5], zoom: 9, duration: 0 }));
    await userEvent.selectOptions(screen.getByLabelText("Species"), "alpha10");
    expect(within(selected).getByText("Select a map point or encounter-list row for details.")).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText("Species"), "all");

    map.handlers.get("click:encounter-points")?.({ features: [{ properties: { source_observation_id: "S2" } }] });
    expect(await screen.findByRole("heading", { name: "alpha 10" })).toBeVisible();
    map.features = [{ properties: { cluster_id: 7, point_count: 23 }, geometry: { type: "Point", coordinates: [-111, 35] } }];
    map.handlers.get("data")?.({});
    const clusterButton = await screen.findByRole("button", { name: "Zoom to cluster containing 23 eligible encounters" });
    expect(clusterButton).toHaveTextContent("23");
    await userEvent.click(clusterButton);
    await waitFor(() => expect(map.clusterZoom).toHaveBeenCalledWith(7));
    map.handlers.get("click:clusters")?.({ features: map.features });
    await waitFor(() => expect(map.clusterZoom).toHaveBeenCalledTimes(2));
    expect(map.easeTo).toHaveBeenLastCalledWith(expect.objectContaining({ center: [-111, 35], zoom: 8 }));

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
});
