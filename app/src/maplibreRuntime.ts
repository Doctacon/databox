import mapLibreScriptUrl from "maplibre-gl/dist/maplibre-gl.js?url";
import type maplibregl from "maplibre-gl";

export type MapLibreRuntime = typeof maplibregl;

declare global {
  interface Window {
    maplibregl?: MapLibreRuntime;
  }
}

const runtimeScriptAttribute = "data-rufous-maplibre-runtime";
let runtimePromise: Promise<MapLibreRuntime> | null = null;

function availableRuntime(): MapLibreRuntime | null {
  const runtime = window.maplibregl;
  return runtime
    && typeof runtime.Map === "function"
    && typeof runtime.Marker === "function"
    && typeof runtime.NavigationControl === "function"
    ? runtime
    : null;
}

export function loadMapLibre(): Promise<MapLibreRuntime> {
  const available = availableRuntime();
  if (available) return Promise.resolve(available);
  if (runtimePromise) return runtimePromise;

  runtimePromise = new Promise<MapLibreRuntime>((resolve, reject) => {
    let script = document.querySelector<HTMLScriptElement>(`script[${runtimeScriptAttribute}]`);
    const created = !script;
    if (!script) {
      script = document.createElement("script");
      script.src = mapLibreScriptUrl;
      script.async = true;
      script.setAttribute(runtimeScriptAttribute, "");
    }
    const removeListeners = () => {
      script?.removeEventListener("load", loaded);
      script?.removeEventListener("error", failed);
    };
    function failed() {
      removeListeners();
      runtimePromise = null;
      script?.remove();
      reject(new Error("The local map renderer could not be loaded."));
    }
    function loaded() {
      const runtime = availableRuntime();
      if (runtime) {
        removeListeners();
        resolve(runtime);
      }
      else failed();
    }

    script.addEventListener("load", loaded);
    script.addEventListener("error", failed);
    if (created) document.head.append(script);
  });
  return runtimePromise;
}
