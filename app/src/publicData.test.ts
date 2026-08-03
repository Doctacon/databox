import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getPublicManifest,
  normalizedPrefix,
  parseArizonaCoordinates,
  searchPublicPlaces,
} from "./publicData";
import type { PublicManifest } from "./publicTypes";

const bounds = { west: -114.82, south: 31.33, east: -109.04, north: 37.01 };
const manifest: PublicManifest = {
  schema_version: 1,
  mode: "public",
  release_mode: "synthetic",
  generated_at: "2026-08-01T12:00:00Z",
  data_version: "fixture",
  region: { code: "US-AZ", name: "Arizona", bounds },
  species: [],
  cells: [],
  place_prefixes: [{ prefix: "pr", path: "/data/places/pr.json", count: 2 }],
  attribution_path: "/data/attribution.json",
  source_policy: { direct_ebird: "excluded", occurrence_source: "synthetic", gbif_dataset_key: null, coverage: "fictional_fixture", required_taxon_key: null, media_source: "none", media_delivery: "none" },
  license_policy: { version: 1, allowed: {}, rejected_counts: {} },
  counts: { species: 0, observations: 0, places: 2, attribution_items: 0, media_items: 0, species_with_media: 0 },
};

afterEach(() => vi.restoreAllMocks());

describe("public static data", () => {
  it("uses normalized two-character place shards", () => {
    expect(normalizedPrefix("Préscott")).toBe("pr");
    expect(normalizedPrefix("A")).toBe("a_");
    expect(normalizedPrefix("---")).toBeNull();
  });

  it("accepts only coordinate pairs inside the release region", () => {
    expect(parseArizonaCoordinates("34.54, -112.47", bounds)).toEqual({ latitude: 34.54, longitude: -112.47 });
    expect(parseArizonaCoordinates("31.50, -114.00", bounds)).toBeNull();
    expect(parseArizonaCoordinates("36.50, -114.70", bounds)).toBeNull();
    expect(parseArizonaCoordinates("39.74, -104.99", bounds)).toBeNull();
    expect(parseArizonaCoordinates("Prescott", bounds)).toBeNull();
  });

  it("loads the declared shard and searches place names without accent sensitivity", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/data/manifest.json") return Promise.resolve(new Response(JSON.stringify(manifest), { status: 200 }));
      if (url === "/data/places/pr.json") return Promise.resolve(new Response(JSON.stringify({
        schema_version: 1,
        prefix: "pr",
        places: [
          { public_id: "2", name: "North Prescott", kind: "Place", source: "usgs_gnis", latitude: 34.6, longitude: -112.4, timezone: "America/Phoenix" },
          { public_id: "1", name: "Préscott, Arizona", kind: "Place", source: "usgs_gnis", latitude: 34.5, longitude: -112.5, timezone: "America/Phoenix" },
        ],
      }), { status: 200 }));
      return Promise.resolve(new Response("not found", { status: 404 }));
    });
    const loaded = await getPublicManifest();
    const places = await searchPublicPlaces("Prescott", loaded);
    expect(places.map((place) => place.name)).toEqual(["Préscott, Arizona", "North Prescott"]);
    expect(fetchMock).toHaveBeenCalledWith("/data/places/pr.json", expect.objectContaining({ credentials: "omit" }));
  });

  it.each([
    ["a mixed media policy", {
      ...manifest,
      source_policy: { ...manifest.source_policy, media_source: "usfws", media_delivery: "none" },
    }],
    ["media counts that do not match species summaries", {
      ...manifest,
      counts: { ...manifest.counts, media_items: 1 },
    }],
  ])("rejects %s", async (_label, invalidManifest) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(invalidManifest), { status: 200 }));
    await expect(getPublicManifest()).rejects.toThrow("This Rufous public data release is not supported.");
  });
});
