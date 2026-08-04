import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getPublicAttribution,
  getPublicManifest,
  getPublicSpecies,
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

const usfwsHero = {
  kind: "photo" as const,
  provider: "usfws" as const,
  media_id: "usfws-rufous-fixture",
  url: `https://rufous-data.loughondata.com/rufous-media/v1/objects/ab/ab${"c".repeat(62)}.webp`,
  source_url: "https://www.fws.gov/media/rufous-hummingbird",
  creator: "USFWS Photographer",
  license: "Public Domain",
  license_url: "https://www.fws.gov/notices",
  attribution_id: "usfws-attribution-fixture",
  scientific_name: "Selasphorus rufus",
  title: "Rufous Hummingbird",
  caption: null,
  alt_text: "A Rufous Hummingbird",
  width: 650,
  height: 488,
  mime_type: "image/webp" as const,
  sha256: `ab${"c".repeat(62)}`,
};
const inaturalistHero = {
  ...usfwsHero,
  provider: "inaturalist" as const,
  media_id: "inaturalist-5938231789",
  source_url: "https://www.inaturalist.org/photos/5938231789",
  creator: "Pat Photographer",
  license: "CC BY 4.0",
  license_url: "https://creativecommons.org/licenses/by/4.0/",
  attribution_id: "inaturalist-attribution-5938231789",
};
const wikimediaHero = {
  ...usfwsHero,
  provider: "wikimedia" as const,
  media_id: `wikimedia-${"1".repeat(24)}`,
  source_url: "https://commons.wikimedia.org/wiki/File:Rufous_Hummingbird.jpg",
  creator: "Commons Photographer",
  license: "CC BY-SA 4.0",
  license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
  attribution_id: `wikimedia-attribution-${"2".repeat(24)}`,
};

function productionManifest(
  mediaSource: PublicManifest["source_policy"]["media_source"],
  provider: "usfws" | "inaturalist" | "wikimedia" = "usfws",
): PublicManifest {
  const withMedia = mediaSource !== "none";
  return {
    ...structuredClone(manifest),
    release_mode: "production",
    source_policy: {
      direct_ebird: "excluded",
      occurrence_source: "gbif",
      gbif_dataset_key: "4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
      coverage: "bounded_sample",
      required_taxon_key: 2476855,
      media_source: mediaSource,
      media_delivery: withMedia ? "immutable_r2" : "none",
    },
    species: withMedia ? [{
      species_code: "gbif-2476855",
      common_name: "Rufous Hummingbird",
      scientific_name: "Selasphorus rufus",
      profile_path: "/data/species/gbif-2476855.json",
      hero_photo: provider === "usfws"
        ? usfwsHero
        : provider === "inaturalist"
          ? inaturalistHero
          : wikimediaHero,
      photo_count: 1,
    }] : [],
    counts: {
      ...manifest.counts,
      species: withMedia ? 1 : 0,
      media_items: withMedia ? 1 : 0,
      species_with_media: withMedia ? 1 : 0,
    },
  };
}

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

  it.each([
    ["USFWS", productionManifest("usfws")],
    ["iNaturalist", productionManifest("inaturalist", "inaturalist")],
    ["Wikimedia Commons", productionManifest("wikimedia", "wikimedia")],
    ["mixed USFWS and iNaturalist", productionManifest("usfws+inaturalist", "inaturalist")],
    ["mixed USFWS and Wikimedia", productionManifest("usfws+wikimedia", "wikimedia")],
    ["mixed iNaturalist and Wikimedia", productionManifest("inaturalist+wikimedia", "wikimedia")],
    ["all reviewed providers", productionManifest("usfws+inaturalist+wikimedia", "wikimedia")],
  ])("accepts the reviewed %s immutable media policy", async (_label, validManifest) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(validManifest), { status: 200 }));
    await expect(getPublicManifest()).resolves.toMatchObject({
      source_policy: validManifest.source_policy,
    });
  });

  it("does not allow a production release to claim no media", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(productionManifest("none")), { status: 200 }));
    await expect(getPublicManifest()).rejects.toThrow("This Rufous public data release is not supported.");
  });

  it("rejects profile media from a provider outside the declared release policy", async () => {
    const production = productionManifest("usfws");
    const profile = {
      schema_version: 1,
      species_code: "gbif-2476855",
      common_name: "Rufous Hummingbird",
      scientific_name: "Selasphorus rufus",
      taxonomic_category: "species",
      family: { common_name: "Hummingbirds", scientific_name: "Trochilidae" },
      order_name: "Caprimulgiformes",
      traits: {},
      evidence: { licensed_occurrence_count: 1, latest_licensed_occurrence_at: "2026-08-01" },
      media: [inaturalistHero],
    };
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => Promise.resolve(new Response(JSON.stringify(
      String(input).endsWith("manifest.json") ? production : profile,
    ), { status: 200 })));
    const loaded = await getPublicManifest();
    await expect(getPublicSpecies(loaded.species[0])).rejects.toThrow("The bird profile did not match the public catalog.");
  });

  it("requires release-level attribution for every declared photo provider", async () => {
    const production = productionManifest("usfws+inaturalist", "inaturalist");
    const incompleteAttribution = {
      schema_version: 1,
      generated_at: "2026-08-03T12:00:00Z",
      sources: [{
        provider: "usfws",
        title: "U.S. Fish and Wildlife Service Media Library",
        url: "https://www.fws.gov/search/images",
        license: "Per-item Public Domain or Creative Commons license",
        license_url: "https://www.fws.gov/notices",
        credit: "Individual creators are credited beside each image.",
      }],
      items: [],
    };
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => Promise.resolve(new Response(JSON.stringify(
      String(input).endsWith("manifest.json") ? production : incompleteAttribution,
    ), { status: 200 })));
    await getPublicManifest();
    await expect(getPublicAttribution("/data/attribution.json"))
      .rejects.toThrow("The attribution shard did not match its manifest entry.");
  });
});
