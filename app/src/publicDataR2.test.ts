import { afterEach, describe, expect, it, vi } from "vitest";

const approvedRoot = "https://rufous-data.loughondata.com/rufous-public";
const releaseId = "a".repeat(64);
const dataVersion = "b".repeat(64);
const manifestSha = "c".repeat(64);
const releaseManifestSha = "d".repeat(64);
const manifestPath = `rufous-public/releases/${releaseId}/objects/data/manifest.json`;
const immutableManifestUrl = `https://rufous-data.loughondata.com/${manifestPath}`;

const fallbackManifest = {
  schema_version: 1,
  mode: "public",
  release_mode: "synthetic",
  generated_at: "2026-08-01T12:00:00Z",
  data_version: "fallback-fixture",
  region: { code: "US-AZ", name: "Arizona", bounds: { west: -114.82, south: 31.33, east: -109.04, north: 37.01 } },
  species: [],
  cells: [],
  place_prefixes: [],
  attribution_path: "/data/attribution.json",
  source_policy: { direct_ebird: "excluded", occurrence_source: "synthetic", gbif_dataset_key: null, coverage: "fictional_fixture", required_taxon_key: null, media_source: "none", media_delivery: "none" },
  license_policy: { version: 1, allowed: {}, rejected_counts: {} },
  counts: { species: 0, observations: 0, places: 0, attribution_items: 0, media_items: 0, species_with_media: 0 },
} as const;

const immutableManifest = {
  ...fallbackManifest,
  data_version: dataVersion,
  species: [{ species_code: "rufhum", common_name: "Rufous Hummingbird", scientific_name: "Selasphorus rufus", profile_path: "/data/species/rufhum.json", hero_photo: null, photo_count: 0 }],
  counts: { ...fallbackManifest.counts, species: 1 },
};

const pointer = {
  schema_version: 1,
  mode: "public-release-pointer",
  release_id: releaseId,
  data_version: dataVersion,
  published_at: "2026-08-02T12:00:00Z",
  manifest_path: manifestPath,
  manifest_sha256: manifestSha,
  release_manifest_sha256: releaseManifestSha,
  release_manifest_key: `rufous-public/releases/${releaseId}/release.json`,
  asset_base_key: `rufous-public/releases/${releaseId}/objects`,
  file_count: 4,
  total_bytes: 4_096,
  previous_releases: [],
} as const;

function json(value: unknown): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } }));
}

function mockDigest(hex = manifestSha) {
  const bytes = new Uint8Array(hex.match(/../g)!.map((value) => Number.parseInt(value, 16)));
  vi.stubGlobal("crypto", { subtle: { digest: vi.fn().mockResolvedValue(bytes.buffer) } });
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("public R2 release resolution", () => {
  it("verifies the immutable manifest and resolves shards inside that release", async () => {
    vi.stubEnv("VITE_RUFOUS_DATA_BASE_URL", approvedRoot);
    mockDigest();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === `${approvedRoot}/manifest.json`) return json(pointer);
      if (url === immutableManifestUrl) return json(immutableManifest);
      if (url === `https://rufous-data.loughondata.com/rufous-public/releases/${releaseId}/objects/data/species/rufhum.json`) {
        return json({ schema_version: 1, species_code: "rufhum", media: [] });
      }
      return Promise.resolve(new Response("not found", { status: 404 }));
    });
    const { getPublicManifest, getPublicSpecies } = await import("./publicData");
    const manifest = await getPublicManifest();
    await getPublicSpecies(manifest.species[0]);

    expect(manifest.data_version).toBe(dataVersion);
    expect(fetchMock).toHaveBeenCalledWith(immutableManifestUrl, expect.objectContaining({ credentials: "omit" }));
    expect(fetchMock).toHaveBeenCalledWith(
      `https://rufous-data.loughondata.com/rufous-public/releases/${releaseId}/objects/data/species/rufhum.json`,
      expect.objectContaining({ credentials: "omit" }),
    );
    expect(crypto.subtle.digest).toHaveBeenCalledWith("SHA-256", expect.any(ArrayBuffer));
  });

  it.each([
    ["network failure", () => Promise.reject(new TypeError("CORS blocked"))],
    ["invalid pointer", () => json({ ...pointer, manifest_path: "https://attacker.example/manifest.json" })],
    ["invalid pointer schema", () => json({ ...pointer, schema_version: 2 })],
  ])("falls back to bundled data after %s", async (_label, remoteResponse) => {
    vi.stubEnv("VITE_RUFOUS_DATA_BASE_URL", approvedRoot);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === `${approvedRoot}/manifest.json`) return remoteResponse();
      if (url === "/data/manifest.json") return json(fallbackManifest);
      return Promise.resolve(new Response("not found", { status: 404 }));
    });
    const { getPublicManifest } = await import("./publicData");

    expect((await getPublicManifest()).data_version).toBe("fallback-fixture");
    expect(fetchMock).toHaveBeenCalledWith("/data/manifest.json", expect.objectContaining({ credentials: "omit" }));
  });

  it("falls back when immutable manifest integrity verification fails", async () => {
    vi.stubEnv("VITE_RUFOUS_DATA_BASE_URL", approvedRoot);
    mockDigest("e".repeat(64));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === `${approvedRoot}/manifest.json`) return json(pointer);
      if (url === immutableManifestUrl) return json(immutableManifest);
      if (url === "/data/manifest.json") return json(fallbackManifest);
      return Promise.resolve(new Response("not found", { status: 404 }));
    });
    const { getPublicManifest } = await import("./publicData");

    expect((await getPublicManifest()).data_version).toBe("fallback-fixture");
  });

  it("rejects a release pointer larger than the 256 MiB public-data ceiling", async () => {
    vi.stubEnv("VITE_RUFOUS_DATA_BASE_URL", approvedRoot);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === `${approvedRoot}/manifest.json`) {
        return json({ ...pointer, total_bytes: (256 * 1024 * 1024) + 1 });
      }
      if (url === "/data/manifest.json") return json(fallbackManifest);
      return Promise.resolve(new Response("not found", { status: 404 }));
    });
    const { getPublicManifest } = await import("./publicData");

    await expect(getPublicManifest()).resolves.toMatchObject({ data_version: "fallback-fixture" });
    expect(fetchMock.mock.calls.map(([input]) => String(input))).not.toContain(immutableManifestUrl);
  });

  it("retries a failed R2 shard only through a same-version bundled release", async () => {
    vi.stubEnv("VITE_RUFOUS_DATA_BASE_URL", approvedRoot);
    mockDigest();
    const profile = { schema_version: 1, species_code: "rufhum", media: [] };
    const r2ProfileUrl = `https://rufous-data.loughondata.com/rufous-public/releases/${releaseId}/objects/data/species/rufhum.json`;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === `${approvedRoot}/manifest.json`) return json(pointer);
      if (url === immutableManifestUrl) return json(immutableManifest);
      if (url === r2ProfileUrl) return Promise.resolve(new Response("missing", { status: 404 }));
      if (url === "/data/manifest.json") return json(immutableManifest);
      if (url === "/data/species/rufhum.json") return json(profile);
      return Promise.resolve(new Response("not found", { status: 404 }));
    });
    const { getPublicManifest, getPublicSpecies } = await import("./publicData");
    const selected = await getPublicManifest();

    await expect(getPublicSpecies(selected.species[0])).resolves.toEqual(profile);
    expect(fetchMock.mock.calls.map(([input]) => String(input))).toContain("/data/manifest.json");
    expect(fetchMock.mock.calls.map(([input]) => String(input))).toContain("/data/species/rufhum.json");
  });

  it("refuses a Pages shard retry when its bundled manifest is a different release", async () => {
    vi.stubEnv("VITE_RUFOUS_DATA_BASE_URL", approvedRoot);
    mockDigest();
    const r2ProfileUrl = `https://rufous-data.loughondata.com/rufous-public/releases/${releaseId}/objects/data/species/rufhum.json`;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === `${approvedRoot}/manifest.json`) return json(pointer);
      if (url === immutableManifestUrl) return json(immutableManifest);
      if (url === r2ProfileUrl) return Promise.resolve(new Response("missing", { status: 404 }));
      if (url === "/data/manifest.json") return json(fallbackManifest);
      if (url === "/data/species/rufhum.json") return json({ schema_version: 1, species_code: "rufhum", media: [] });
      return Promise.resolve(new Response("not found", { status: 404 }));
    });
    const { getPublicManifest, getPublicSpecies } = await import("./publicData");
    const selected = await getPublicManifest();

    await expect(getPublicSpecies(selected.species[0])).rejects.toThrow(/bundled fallback is a different release/);
    expect(fetchMock.mock.calls.map(([input]) => String(input))).not.toContain("/data/species/rufhum.json");
  });

  it("times out a stalled remote pointer and leaves the bundled fallback caller-controlled", async () => {
    vi.useFakeTimers();
    vi.stubEnv("VITE_RUFOUS_DATA_BASE_URL", approvedRoot);
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url === "/data/manifest.json") return json(fallbackManifest);
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
      });
    });
    const { getPublicManifest } = await import("./publicData");
    const pending = getPublicManifest();
    await vi.advanceTimersByTimeAsync(3_001);

    await expect(pending).resolves.toMatchObject({ data_version: "fallback-fixture" });
  });

  it("times out a stalled R2 shard before retrying the same release from Pages", async () => {
    vi.useFakeTimers();
    vi.stubEnv("VITE_RUFOUS_DATA_BASE_URL", approvedRoot);
    mockDigest();
    const profile = { schema_version: 1, species_code: "rufhum", media: [] };
    const r2ProfileUrl = `https://rufous-data.loughondata.com/rufous-public/releases/${releaseId}/objects/data/species/rufhum.json`;
    let remoteShardSignal: AbortSignal | null | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url === `${approvedRoot}/manifest.json`) return json(pointer);
      if (url === immutableManifestUrl) return json(immutableManifest);
      if (url === r2ProfileUrl) {
        remoteShardSignal = init?.signal;
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        });
      }
      if (url === "/data/manifest.json") return json(immutableManifest);
      if (url === "/data/species/rufhum.json") return json(profile);
      return Promise.resolve(new Response("not found", { status: 404 }));
    });
    const { getPublicManifest, getPublicSpecies } = await import("./publicData");
    const selected = await getPublicManifest();
    const pending = getPublicSpecies(selected.species[0]);
    await vi.advanceTimersByTimeAsync(3_001);

    await expect(pending).resolves.toEqual(profile);
    expect(remoteShardSignal?.aborted).toBe(true);
  });

  it("never contacts an unapproved configured host", async () => {
    vi.stubEnv("VITE_RUFOUS_DATA_BASE_URL", "https://example.r2.dev/rufous-public");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      if (String(input) === "/data/manifest.json") return json(fallbackManifest);
      return Promise.resolve(new Response("not found", { status: 404 }));
    });
    const { getPublicManifest } = await import("./publicData");

    await expect(getPublicManifest()).resolves.toMatchObject({ data_version: "fallback-fixture" });
    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual(["/data/manifest.json"]);
  });
});
