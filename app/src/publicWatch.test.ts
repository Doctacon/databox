import { afterEach, describe, expect, it, vi } from "vitest";
import type { PublicManifest, PublicWatch } from "./publicTypes";
import {
  distanceMiles,
  evaluatePublicWatch,
  PUBLIC_WATCH_STORAGE_KEY,
  readPublicWatches,
  writePublicWatches,
} from "./publicWatch";

const watch: PublicWatch = {
  id: "watch-1",
  species_code: "mexjay",
  bird_name: "Mexican Jay",
  center_name: "Prescott, Arizona",
  center_latitude: 34.54,
  center_longitude: -112.47,
  center_timezone: "America/Phoenix",
  radius_miles: 25,
  outing_date: "2026-08-02",
  created_at: "2026-08-01T12:00:00Z",
};

const manifest: PublicManifest = {
  schema_version: 1, mode: "public", release_mode: "synthetic", generated_at: "2026-08-01T12:00:00Z", data_version: "fixture",
  region: { code: "US-AZ", name: "Arizona", bounds: { west: -114.82, south: 31.33, east: -109.04, north: 37.01 } },
  species: [],
  cells: [
    { cell_id: "near", path: "/data/cells/near.json", observation_count: 2, bounds: { west: -113, south: 34, east: -112, north: 35 } },
    { cell_id: "far", path: "/data/cells/far.json", observation_count: 1, bounds: { west: -111, south: 32, east: -110, north: 33 } },
  ],
  place_prefixes: [], attribution_path: "/data/attribution.json",
  source_policy: { direct_ebird: "excluded", occurrence_source: "synthetic", gbif_dataset_key: null, coverage: "fictional_fixture", required_taxon_key: null, media_source: "none", media_delivery: "none" },
  license_policy: { version: 1, allowed: {}, rejected_counts: {} },
  counts: { species: 0, observations: 3, places: 0, attribution_items: 0, media_items: 0, species_with_media: 0 },
};

afterEach(() => vi.restoreAllMocks());

describe("browser-only watches", () => {
  it("stores only validated watches in local storage", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value); },
    };
    writePublicWatches([watch], storage);
    expect(readPublicWatches(storage)).toEqual([watch]);
    values.set(PUBLIC_WATCH_STORAGE_KEY, JSON.stringify([{ email: "never@example.com" }]));
    expect(readPublicWatches(storage)).toEqual([]);
  });

  it("loads only intersecting cells and filters matches locally", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      schema_version: 1,
      cell_id: "near",
      bounds: manifest.cells[0].bounds,
      observations: [
        { public_id: "recent", species_code: "mexjay", observed_at: "2026-07-31T12:00:00Z", count: 2, count_display: "2 birds", is_notable: false, location: { name: "Near Site", latitude: 34.55, longitude: -112.45, kind: "site", timezone: "America/Phoenix" } },
        { public_id: "other", species_code: "gilwoo", observed_at: "2026-07-31T13:00:00Z", count: 1, count_display: "1 bird", is_notable: false, location: { name: "Near Site", latitude: 34.55, longitude: -112.45, kind: "site", timezone: "America/Phoenix" } },
      ],
    }), { status: 200 }));
    const result = await evaluatePublicWatch(watch, manifest);
    expect(result.loaded_cell_ids).toEqual(["near"]);
    expect(result.matches).toHaveLength(1);
    expect(result.matches[0].public_id).toBe("recent");
    expect(result.matches[0].distance_miles).toBeLessThan(2);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(distanceMiles(34.54, -112.47, 34.54, -112.47)).toBe(0);
  });
});
