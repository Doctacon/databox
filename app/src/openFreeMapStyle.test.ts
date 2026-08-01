import { afterEach, describe, expect, it, vi } from "vitest";

const validStyle = {
  version: 8,
  sprite: "https://tiles.openfreemap.org/sprites/ofm/sprite",
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  sources: {
    openmaptiles: { type: "vector", url: "https://tiles.openfreemap.org/planet" },
    shadedRelief: {
      type: "raster",
      tiles: ["https://tiles.openfreemap.org/relief/{z}/{x}/{y}.webp"],
    },
  },
  layers: [{ id: "background", type: "background" }],
};

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("OpenFreeMap style loader", () => {
  it("requests only the fixed HTTPS Positron endpoint with privacy-safe options", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue(validStyle) });
    vi.stubGlobal("fetch", fetchMock);
    const { loadOpenFreeMapStyle, OPEN_FREE_MAP_STYLE_URL } = await import("./openFreeMapStyle");

    await expect(loadOpenFreeMapStyle()).resolves.toEqual({ status: "ready", style: validStyle });
    expect(OPEN_FREE_MAP_STYLE_URL).toBe("https://tiles.openfreemap.org/styles/positron");
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(OPEN_FREE_MAP_STYLE_URL, expect.objectContaining({
      credentials: "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: expect.any(AbortSignal),
    }));
  });

  it("shares the in-flight request and caches the validated result", async () => {
    let resolveFetch!: (response: { ok: boolean; json: () => Promise<unknown> }) => void;
    const fetchMock = vi.fn(() => new Promise<{ ok: boolean; json: () => Promise<unknown> }>((resolve) => {
      resolveFetch = resolve;
    }));
    vi.stubGlobal("fetch", fetchMock);
    const { loadOpenFreeMapStyle } = await import("./openFreeMapStyle");

    const first = loadOpenFreeMapStyle();
    const second = loadOpenFreeMapStyle();
    expect(second).toBe(first);
    expect(fetchMock).toHaveBeenCalledOnce();

    resolveFetch({ ok: true, json: async () => validStyle });
    const result = await first;
    expect(result).toEqual({ status: "ready", style: validStyle });
    await expect(loadOpenFreeMapStyle()).resolves.toBe(result);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it.each([
    { version: 7, sources: validStyle.sources, layers: validStyle.layers },
    { version: 8, sources: {}, layers: validStyle.layers },
    { version: 8, sources: validStyle.sources, layers: [] },
    { version: 8, sources: validStyle.sources, layers: [{ id: "", type: "background" }] },
  ])("fails closed for a malformed style", async (candidate) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(candidate),
    }));
    const { loadOpenFreeMapStyle } = await import("./openFreeMapStyle");

    await expect(loadOpenFreeMapStyle()).resolves.toEqual({ status: "fallback" });
  });

  it.each([
    ["insecure source URL", { ...validStyle, sources: { openmaptiles: { type: "vector", url: "http://tiles.openfreemap.org/planet" } } }],
    ["lookalike source URL", { ...validStyle, sources: { openmaptiles: { type: "vector", url: "https://tiles.openfreemap.org.example.com/planet" } } }],
    ["credential-bearing sprite URL", { ...validStyle, sprite: "https://user@tiles.openfreemap.org/sprite" }],
    ["explicit-port glyph URL", { ...validStyle, glyphs: "https://tiles.openfreemap.org:443/fonts/{fontstack}/{range}.pbf" }],
    ["untrusted protocol-relative tile URL", {
      ...validStyle,
      sources: { raster: { type: "raster", tiles: ["//tiles.example.com/{z}/{x}/{y}.png"] } },
    }],
    ["non-HTTPS network scheme", { ...validStyle, sprite: "data:application/json;base64,e30=" }],
    ["deeply nested untrusted resource", {
      ...validStyle,
      metadata: { provider: { futureResource: "https://tiles.example.com/style-extension.json" } },
    }],
  ])("rejects a %s", async (_label, candidate) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(candidate),
    }));
    const { loadOpenFreeMapStyle } = await import("./openFreeMapStyle");

    await expect(loadOpenFreeMapStyle()).resolves.toEqual({ status: "fallback" });
  });

  it("accepts trusted absolute and protocol-relative resources without credentials or ports", async () => {
    const candidate = {
      ...validStyle,
      sprite: "//tiles.openfreemap.org/sprites/ofm/sprite",
      sources: {
        ...validStyle.sources,
        openmaptiles: { type: "vector", url: "//tiles.openfreemap.org/planet" },
      },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(candidate),
    }));
    const { loadOpenFreeMapStyle } = await import("./openFreeMapStyle");

    await expect(loadOpenFreeMapStyle()).resolves.toEqual({ status: "ready", style: candidate });
  });

  it("returns the same safe fallback for provider, parsing, and network failures", async () => {
    for (const response of [
      () => Promise.resolve({ ok: false, json: vi.fn() }),
      () => Promise.resolve({ ok: true, json: vi.fn().mockRejectedValue(new Error("raw parser detail")) }),
      () => Promise.reject(new Error("raw network detail")),
    ]) {
      vi.resetModules();
      vi.stubGlobal("fetch", vi.fn(response));
      const { loadOpenFreeMapStyle } = await import("./openFreeMapStyle");
      const result = await loadOpenFreeMapStyle();
      expect(result).toEqual({ status: "fallback" });
      expect(JSON.stringify(result)).not.toMatch(/raw|network|parser/i);
    }
  });

  it("aborts a stalled request at the bounded timeout and returns the safe fallback", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("provider detail", "AbortError")));
    }));
    vi.stubGlobal("fetch", fetchMock);
    const { loadOpenFreeMapStyle, OPEN_FREE_MAP_STYLE_TIMEOUT_MS } = await import("./openFreeMapStyle");

    const result = loadOpenFreeMapStyle();
    await vi.advanceTimersByTimeAsync(OPEN_FREE_MAP_STYLE_TIMEOUT_MS);
    await expect(result).resolves.toEqual({ status: "fallback" });
    expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
  });
});
