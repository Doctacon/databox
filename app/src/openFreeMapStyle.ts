import type { StyleSpecification } from "maplibre-gl";

export const OPEN_FREE_MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/positron" as const;
export const OPEN_FREE_MAP_STYLE_TIMEOUT_MS = 4_000;

export type OpenFreeMapStyleResult =
  | { status: "ready"; style: StyleSpecification }
  | { status: "fallback" };

const fallbackResult: OpenFreeMapStyleResult = Object.freeze({ status: "fallback" });
let styleRequest: Promise<OpenFreeMapStyleResult> | null = null;
const resourceKeys = new Set(["data", "glyphs", "sprite", "tiles", "url", "urls"]);
const networkSchemeWithoutAuthority = /^(?:blob|data|file|filesystem|ftp|ftps|http|https|ipfs|mapbox|pmtiles|s3|ws|wss):/i;
const schemeWithAuthority = /^[a-z][a-z\d+.-]*:[/\\]{2}/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNetworkResource(value: string, key: string | null): boolean {
  const candidate = value.trim();
  return candidate.startsWith("//") || candidate.startsWith("\\\\")
    || schemeWithAuthority.test(candidate) || networkSchemeWithoutAuthority.test(candidate)
    || (key !== null && resourceKeys.has(key) && /^[a-z][a-z\d+.-]*:/i.test(candidate));
}

function isTrustedResource(value: string): boolean {
  const candidate = value.trim();
  const authority = candidate.match(/^(?:https:)?\/\/([^/?#]*)/i)?.[1];
  if (authority === undefined || authority.toLowerCase() !== "tiles.openfreemap.org") return false;
  try {
    const parsed = new URL(candidate, OPEN_FREE_MAP_STYLE_URL);
    return parsed.protocol === "https:" && parsed.origin === "https://tiles.openfreemap.org"
      && parsed.hostname === "tiles.openfreemap.org" && parsed.port === ""
      && parsed.username === "" && parsed.password === "";
  }
  catch {
    return false;
  }
}

function hasOnlyTrustedResources(value: unknown, key: string | null = null): boolean {
  if (typeof value === "string") {
    return !isNetworkResource(value, key) || isTrustedResource(value);
  }
  if (Array.isArray(value)) return value.every((item) => hasOnlyTrustedResources(item, key));
  if (!isRecord(value)) return true;
  return Object.entries(value).every(([childKey, child]) => hasOnlyTrustedResources(child, childKey));
}

function isStyleSpecification(value: unknown): value is StyleSpecification {
  if (!isRecord(value) || value.version !== 8 || !isRecord(value.sources)
    || Object.keys(value.sources).length === 0 || !Array.isArray(value.layers)
    || value.layers.length === 0 || !hasOnlyTrustedResources(value)) return false;

  return Object.values(value.sources).every(isRecord)
    && value.layers.every((layer) => isRecord(layer)
      && typeof layer.id === "string" && layer.id.trim().length > 0
      && typeof layer.type === "string" && layer.type.trim().length > 0);
}

async function requestStyle(): Promise<OpenFreeMapStyleResult> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), OPEN_FREE_MAP_STYLE_TIMEOUT_MS);
  try {
    const response = await fetch(OPEN_FREE_MAP_STYLE_URL, {
      cache: "force-cache",
      credentials: "omit",
      headers: { Accept: "application/json" },
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
    });
    if (!response.ok) return fallbackResult;
    const candidate: unknown = await response.json();
    return isStyleSpecification(candidate)
      ? { status: "ready", style: candidate }
      : fallbackResult;
  }
  catch {
    return fallbackResult;
  }
  finally {
    globalThis.clearTimeout(timeout);
  }
}

/**
 * Loads the fixed OpenFreeMap Positron style once per page session.
 *
 * Failures intentionally collapse to a detail-free fallback signal so callers
 * can retain the bundled local map without exposing provider or network errors.
 */
export function loadOpenFreeMapStyle(): Promise<OpenFreeMapStyleResult> {
  styleRequest ??= requestStyle();
  return styleRequest;
}
