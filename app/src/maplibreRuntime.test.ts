import { afterEach, describe, expect, it, vi } from "vitest";

function fakeRuntime() {
  return {
    Map: class {},
    Marker: class {},
    NavigationControl: class {},
  };
}

afterEach(() => {
  document.querySelectorAll("script[data-rufous-maplibre-runtime]").forEach((script) => script.remove());
  Reflect.deleteProperty(window, "maplibregl");
  vi.resetModules();
});

describe("local MapLibre runtime loader", () => {
  it("loads one same-origin asset on demand and shares the in-flight request", async () => {
    const { loadMapLibre } = await import("./maplibreRuntime");
    const first = loadMapLibre();
    const second = loadMapLibre();
    const script = document.querySelector<HTMLScriptElement>("script[data-rufous-maplibre-runtime]");

    expect(second).toBe(first);
    expect(script).not.toBeNull();
    expect(new URL(script!.src).origin).toBe(window.location.origin);
    expect(script!.src).toMatch(/maplibre-gl.*\.js/);

    const runtime = fakeRuntime();
    Object.defineProperty(window, "maplibregl", { configurable: true, value: runtime });
    script!.dispatchEvent(new Event("load"));
    await expect(first).resolves.toBe(runtime);
  });

  it("fails closed, removes a failed asset, and permits a bounded retry", async () => {
    const { loadMapLibre } = await import("./maplibreRuntime");
    const first = loadMapLibre();
    const failedScript = document.querySelector<HTMLScriptElement>("script[data-rufous-maplibre-runtime]");
    failedScript!.dispatchEvent(new Event("error"));

    await expect(first).rejects.toThrow("local map renderer could not be loaded");
    expect(failedScript).not.toBeInTheDocument();

    const retry = loadMapLibre();
    const retryScript = document.querySelector<HTMLScriptElement>("script[data-rufous-maplibre-runtime]");
    expect(retryScript).not.toBe(failedScript);
    retryScript!.dispatchEvent(new Event("error"));
    await expect(retry).rejects.toThrow("local map renderer could not be loaded");
  });
});
