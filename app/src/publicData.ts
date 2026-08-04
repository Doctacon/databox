import type {
  PublicAttribution,
  PublicBounds,
  PublicCell,
  PublicManifest,
  PublicMediaSource,
  PublicPlace,
  PublicPlaceShard,
  PublicReleasePointer,
  PublicSpeciesProfile,
  PublicSpeciesSummary,
} from "./publicTypes";
import { publicCatalogPhoto } from "./publicAdapters/media";
import { isPublicSpeciesCode } from "./publicSpeciesCode";
import arizonaBoundariesRaw from "./assets/arizona-boundaries.geojson?raw";

const APPROVED_REMOTE_DATA_ROOT = "https://rufous-data.loughondata.com/rufous-public";
const configuredValue = import.meta.env.VITE_RUFOUS_DATA_BASE_URL?.trim();
const configuredDataRoot = configuredValue === APPROVED_REMOTE_DATA_ROOT ? configuredValue : undefined;
const DATA_ROOT = configuredDataRoot || "/data";
const SAME_ORIGIN_DATA_ROOT = "/data";
const REMOTE_TIMEOUT_MS = 3_000;
const MAX_RELEASE_BYTES = 256 * 1024 * 1024;
let activeDataRoot = SAME_ORIGIN_DATA_ROOT;
let activeDataVersion: string | null = null;
let activeMediaSource: PublicMediaSource = "none";
let fallbackManifestPromise: Promise<PublicManifest> | null = null;
const SAFE_DATA_PATH = /^\/?(?:data\/)?(?:releases\/[a-f0-9_-]+\/)?(?:manifest|attribution|catalog|species\/[a-z0-9_-]+|cells\/[a-z0-9_-]+|places\/[a-z0-9_]+)\.json$/i;
const BOUNDARY_TOLERANCE = 1e-9;
const EBIRD_EOD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e";
const RUFOUS_TAXON_KEY = 2476855;
const MEDIA_SOURCES: readonly PublicMediaSource[] = ["none", "usfws", "inaturalist", "usfws+inaturalist"];
const NONEMPTY_MEDIA_SOURCES: ReadonlySet<PublicMediaSource> = new Set(["usfws", "inaturalist", "usfws+inaturalist"]);

export const ARIZONA_STATE_RING = (JSON.parse(arizonaBoundariesRaw) as {
  features: Array<{
    properties?: { kind?: string };
    geometry?: { type?: string; coordinates?: number[][][] };
  }>;
}).features.find((feature) => feature.properties?.kind === "state")?.geometry?.coordinates?.[0] ?? [];

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    signal,
    headers: { Accept: "application/json" },
    credentials: "omit",
  });
  if (!response.ok) throw new Error(`Public data is unavailable (${response.status}).`);
  return response.json() as Promise<T>;
}

async function fetchVerifiedJson<T>(
  path: string,
  expectedSha256: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, {
    signal,
    headers: { Accept: "application/json" },
    credentials: "omit",
  });
  if (!response.ok) throw new Error(`Public data is unavailable (${response.status}).`);
  const bytes = await response.arrayBuffer();
  if (!crypto.subtle) throw new Error("This browser cannot verify the public release.");
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const actual = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  if (actual !== expectedSha256) throw new Error("The immutable Rufous manifest failed integrity verification.");
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)) as T;
  } catch {
    throw new Error("The immutable Rufous manifest is not valid UTF-8 JSON.");
  }
}

function joinPath(base: string, relative: string): string {
  return `${base.replace(/\/+$/, "")}/${relative.replace(/^\/+/, "")}`;
}

function rootPath(relative: string): string {
  return joinPath(activeDataRoot, relative);
}

function timedSignal(caller?: AbortSignal): { signal: AbortSignal; cleanup: () => void } {
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort(caller?.reason);
  if (caller?.aborted) abortFromCaller();
  else caller?.addEventListener("abort", abortFromCaller, { once: true });
  const timer = window.setTimeout(() => controller.abort(new DOMException("Timed out", "TimeoutError")), REMOTE_TIMEOUT_MS);
  return {
    signal: controller.signal,
    cleanup: () => {
      window.clearTimeout(timer);
      caller?.removeEventListener("abort", abortFromCaller);
    },
  };
}

function objectKeyUrl(base: string, key: string): string {
  if (/^https:\/\//i.test(base)) {
    const configured = new URL(base);
    return new URL(`/${key.replace(/^\/+/, "")}`, configured.origin).href;
  }
  return `/${key.replace(/^\/+/, "")}`;
}

function dataRelativePath(path: string, expectedDirectory: "species" | "cells" | "places" | "root"): string {
  if (path.includes("..") || !path.endsWith(".json") || !SAFE_DATA_PATH.test(path)) {
    throw new Error("The public data manifest contains an invalid shard path.");
  }
  const normalized = path.replace(/^\/+/, "").replace(/^data\//, "");
  const expected = expectedDirectory === "root" ? "" : `${expectedDirectory}/`;
  const releaseRelative = normalized.replace(/^releases\/[a-f0-9_-]+\//i, "");
  if (!releaseRelative.startsWith(expected)) {
    throw new Error("The public data manifest contains an invalid shard path.");
  }
  return releaseRelative;
}

function safePath(path: string, expectedDirectory: "species" | "cells" | "places" | "root"): string {
  const releaseRelative = dataRelativePath(path, expectedDirectory);
  if (/^https:\/\//i.test(activeDataRoot)) {
    return rootPath(releaseRelative);
  }
  if (activeDataRoot !== DATA_ROOT) return rootPath(releaseRelative);
  return path.startsWith("/") ? path : rootPath(releaseRelative);
}

function normalizedSearchKey(value: string): string {
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase().replace(/[^a-z0-9]/g, "");
}

export function normalizedPrefix(value: string): string | null {
  const normalized = normalizedSearchKey(value);
  if (!normalized) return null;
  return normalized.length === 1 ? `${normalized}_` : normalized.slice(0, 2);
}

function mediaProviders(source: PublicMediaSource): ReadonlySet<"usfws" | "inaturalist"> {
  if (source === "usfws") return new Set(["usfws"]);
  if (source === "inaturalist") return new Set(["inaturalist"]);
  if (source === "usfws+inaturalist") return new Set(["usfws", "inaturalist"]);
  return new Set();
}

function recognizedMediaSource(value: unknown): PublicMediaSource | null {
  return typeof value === "string" && MEDIA_SOURCES.includes(value as PublicMediaSource)
    ? value as PublicMediaSource
    : null;
}

function validateManifest(manifest: PublicManifest): PublicManifest {
  const expectedOccurrenceSource = manifest.release_mode === "production" ? "gbif" : "synthetic";
  const expectedDatasetKey = manifest.release_mode === "production" ? EBIRD_EOD_DATASET_KEY : null;
  const expectedCoverage = manifest.release_mode === "production" ? "bounded_sample" : "fictional_fixture";
  const expectedRequiredTaxon = manifest.release_mode === "production" ? RUFOUS_TAXON_KEY : null;
  const mediaSource = recognizedMediaSource(manifest.source_policy?.media_source);
  const validMediaPolicy = manifest.release_mode === "production"
    ? mediaSource !== null && NONEMPTY_MEDIA_SOURCES.has(mediaSource)
      && manifest.source_policy?.media_delivery === "immutable_r2"
    : (manifest.source_policy?.media_source === "none" && manifest.source_policy?.media_delivery === "none")
      || (mediaSource !== null && NONEMPTY_MEDIA_SOURCES.has(mediaSource)
        && manifest.source_policy?.media_delivery === "immutable_r2");
  const allowedMediaProviders: ReadonlySet<string> = mediaSource
    ? mediaProviders(mediaSource)
    : new Set<string>();
  const mediaItems = Array.isArray(manifest.species)
    ? manifest.species.reduce((total, species) => total + species.photo_count, 0)
    : -1;
  const speciesWithMedia = Array.isArray(manifest.species)
    ? manifest.species.filter((species) => species.photo_count > 0).length
    : -1;
  if (
    manifest.schema_version !== 1
    || manifest.mode !== "public"
    || !["synthetic", "production"].includes(manifest.release_mode)
    || manifest.region.code !== "US-AZ"
    || manifest.source_policy?.direct_ebird !== "excluded"
    || manifest.source_policy?.occurrence_source !== expectedOccurrenceSource
    || manifest.source_policy?.gbif_dataset_key !== expectedDatasetKey
    || manifest.source_policy?.coverage !== expectedCoverage
    || manifest.source_policy?.required_taxon_key !== expectedRequiredTaxon
    || !validMediaPolicy
    || manifest.license_policy?.version !== 1
    || !Number.isInteger(manifest.counts?.attribution_items)
    || !Number.isSafeInteger(manifest.counts?.media_items) || manifest.counts.media_items < 0
    || !Number.isSafeInteger(manifest.counts?.species_with_media) || manifest.counts.species_with_media < 0
    || !Array.isArray(manifest.species)
    || manifest.species.some((species) => !isPublicSpeciesCode(species.species_code)
      || !Number.isSafeInteger(species.photo_count) || species.photo_count < 0
      || !("hero_photo" in species)
      || (species.photo_count === 0 && species.hero_photo !== null)
      || (species.photo_count > 0 && species.hero_photo === null)
      || (species.hero_photo !== null && !allowedMediaProviders.has(species.hero_photo.provider)))
    || manifest.counts?.media_items !== mediaItems
    || manifest.counts?.species_with_media !== speciesWithMedia
    || (mediaSource === "none" && (mediaItems !== 0 || speciesWithMedia !== 0))
    || (mediaSource !== "none" && (mediaItems === 0 || speciesWithMedia === 0))
  ) {
    throw new Error("This Rufous public data release is not supported.");
  }
  return manifest;
}

function releasePointer(value: PublicManifest | PublicReleasePointer): PublicReleasePointer {
  const pointer = value as PublicReleasePointer;
  const sha256 = (item: unknown): item is string => typeof item === "string" && /^[0-9a-f]{64}$/.test(item);
  const safeKey = (key: unknown): key is string => typeof key === "string"
    && /^[a-z0-9._/-]{1,512}$/i.test(key) && !key.includes("..") && !key.startsWith("/");
  if (
    pointer.schema_version !== 1
    || pointer.mode !== "public-release-pointer"
    || !sha256(pointer.release_id)
    || !sha256(pointer.data_version)
    || !sha256(pointer.manifest_sha256)
    || !sha256(pointer.release_manifest_sha256)
    || typeof pointer.published_at !== "string" || !Number.isFinite(Date.parse(pointer.published_at))
    || !safeKey(pointer.manifest_path)
    || !safeKey(pointer.release_manifest_key)
    || !safeKey(pointer.asset_base_key)
    || !Number.isSafeInteger(pointer.file_count) || pointer.file_count < 0 || pointer.file_count > 20_000
    || !Number.isSafeInteger(pointer.total_bytes) || pointer.total_bytes < 0 || pointer.total_bytes > MAX_RELEASE_BYTES
    || !Array.isArray(pointer.previous_releases) || pointer.previous_releases.length > 100
  ) throw new Error("This Rufous public release pointer is not supported.");
  const assetBase = `rufous-public/releases/${pointer.release_id}/objects`;
  if (pointer.asset_base_key !== assetBase
    || pointer.manifest_path !== `${assetBase}/data/manifest.json`
    || pointer.release_manifest_key !== `rufous-public/releases/${pointer.release_id}/release.json`) {
    throw new Error("This Rufous public release pointer is not supported.");
  }
  return pointer;
}

async function resolveManifest(
  base: string,
  signal: AbortSignal | undefined,
  allowPointer: boolean,
): Promise<{ manifest: PublicManifest; dataRoot: string }> {
  const rootDocument = await fetchJson<PublicManifest | PublicReleasePointer>(joinPath(base, "manifest.json"), signal);
  if (rootDocument.mode === "public") {
    return { manifest: validateManifest(rootDocument), dataRoot: base };
  }
  if (!allowPointer) throw new Error("This Rufous public data release is not supported.");
  const pointer = releasePointer(rootDocument);
  const manifestUrl = objectKeyUrl(base, pointer.manifest_path);
  const manifest = validateManifest(await fetchVerifiedJson<PublicManifest>(manifestUrl, pointer.manifest_sha256, signal));
  if (manifest.data_version !== pointer.data_version) {
    throw new Error("The Rufous release pointer did not match its immutable manifest.");
  }
  return {
    manifest,
    dataRoot: manifestUrl.slice(0, -"/manifest.json".length),
  };
}

export async function getPublicManifest(signal?: AbortSignal): Promise<PublicManifest> {
  let resolution: { manifest: PublicManifest; dataRoot: string };
  if (configuredDataRoot) {
    const timed = timedSignal(signal);
    try {
      resolution = await resolveManifest(DATA_ROOT, timed.signal, true);
    } catch (configuredFailure) {
      if (signal?.aborted) throw configuredFailure;
      resolution = await resolveManifest(SAME_ORIGIN_DATA_ROOT, signal, false);
    } finally {
      timed.cleanup();
    }
  } else {
    resolution = await resolveManifest(SAME_ORIGIN_DATA_ROOT, signal, false);
  }
  // Swap only after the complete pointer + immutable manifest chain has passed validation.
  activeDataRoot = resolution.dataRoot;
  activeDataVersion = resolution.manifest.data_version;
  activeMediaSource = resolution.manifest.source_policy.media_source;
  fallbackManifestPromise = null;
  return resolution.manifest;
}

async function sameReleasePagesManifest(signal?: AbortSignal): Promise<PublicManifest> {
  if (!activeDataVersion) throw new Error("The active Rufous release is unavailable.");
  if (!fallbackManifestPromise) {
    const expectedVersion = activeDataVersion;
    const pending = resolveManifest(SAME_ORIGIN_DATA_ROOT, signal, false).then((resolution) => {
      if (resolution.manifest.data_version !== expectedVersion) {
        throw new Error("The published data shard is unavailable and the bundled fallback is a different release.");
      }
      activeDataRoot = SAME_ORIGIN_DATA_ROOT;
      activeMediaSource = resolution.manifest.source_policy.media_source;
      return resolution.manifest;
    }).catch((reason: unknown) => {
      if (fallbackManifestPromise === pending) fallbackManifestPromise = null;
      throw reason;
    });
    fallbackManifestPromise = pending;
  }
  return fallbackManifestPromise;
}

async function withCoherentShardFallback<T>(
  attempt: (requestSignal?: AbortSignal) => Promise<T>,
  fallback: (manifest: PublicManifest) => Promise<T>,
  signal?: AbortSignal,
): Promise<T> {
  const startedOnRemote = activeDataRoot.startsWith(`${APPROVED_REMOTE_DATA_ROOT}/releases/`);
  if (!startedOnRemote) return attempt(signal);

  const timed = timedSignal(signal);
  try {
    return await attempt(timed.signal);
  } catch (reason) {
    if (signal?.aborted) throw reason;
    const pagesManifest = await sameReleasePagesManifest(signal);
    return fallback(pagesManifest);
  } finally {
    timed.cleanup();
  }
}

export async function getPublicSpecies(
  species: PublicSpeciesSummary,
  signal?: AbortSignal,
): Promise<PublicSpeciesProfile> {
  if (!isPublicSpeciesCode(species.species_code)) throw new Error("Invalid species code.");
  const path = safePath(species.profile_path, "species");
  const load = async (url: string, requestSignal?: AbortSignal) => {
    const profile = await fetchJson<PublicSpeciesProfile>(url, requestSignal);
    if (profile.schema_version !== 1 || profile.species_code !== species.species_code
      || !Array.isArray(profile.media)
      || profile.media.some((item) => !mediaProviders(activeMediaSource).has(item.provider))
      || profile.media.some((item) => publicCatalogPhoto(item, profile.scientific_name, "") === null)
      || profile.media.length !== species.photo_count
      || (species.hero_photo === null
        ? profile.media.length !== 0
        : profile.media[0]?.media_id !== species.hero_photo.media_id)) {
      throw new Error("The bird profile did not match the public catalog.");
    }
    return profile;
  };
  return withCoherentShardFallback(
    (requestSignal) => load(path, requestSignal),
    (manifest) => {
      const fallbackSpecies = manifest.species.find((item) => item.species_code === species.species_code);
      if (!fallbackSpecies) throw new Error("The bird profile is missing from the coherent bundled fallback.");
      return load(joinPath(SAME_ORIGIN_DATA_ROOT, dataRelativePath(fallbackSpecies.profile_path, "species")), signal);
    },
    signal,
  );
}

export async function getPublicCell(path: string, signal?: AbortSignal): Promise<PublicCell> {
  const relative = dataRelativePath(path, "cells");
  const primary = safePath(path, "cells");
  const expectedCellId = relative.slice("cells/".length, -".json".length);
  const load = async (url: string, requestSignal?: AbortSignal) => {
    const cell = await fetchJson<PublicCell>(url, requestSignal);
    if (cell.schema_version !== 1 || cell.cell_id !== expectedCellId || !Array.isArray(cell.observations)) {
      throw new Error("The observation shard did not match its manifest entry.");
    }
    return cell;
  };
  return withCoherentShardFallback(
    (requestSignal) => load(primary, requestSignal),
    (manifest) => {
      const fallbackCell = manifest.cells.find((item) => dataRelativePath(item.path, "cells") === relative);
      if (!fallbackCell) throw new Error("The observation shard is missing from the coherent bundled fallback.");
      return load(joinPath(SAME_ORIGIN_DATA_ROOT, dataRelativePath(fallbackCell.path, "cells")), signal);
    },
    signal,
  );
}

export async function getPublicAttribution(path: string, signal?: AbortSignal): Promise<PublicAttribution> {
  const primary = safePath(path, "root");
  const load = async (url: string, requestSignal?: AbortSignal) => {
    const attribution = await fetchJson<PublicAttribution>(url, requestSignal);
    const attributedProviders = Array.isArray(attribution.sources)
      ? new Set(attribution.sources.map((source) => source.provider))
      : new Set<string>();
    if (attribution.schema_version !== 1 || !Array.isArray(attribution.sources) || !Array.isArray(attribution.items)
      || [...mediaProviders(activeMediaSource)].some((provider) => !attributedProviders.has(provider))) {
      throw new Error("The attribution shard did not match its manifest entry.");
    }
    return attribution;
  };
  return withCoherentShardFallback(
    (requestSignal) => load(primary, requestSignal),
    (manifest) => load(joinPath(
      SAME_ORIGIN_DATA_ROOT,
      dataRelativePath(manifest.attribution_path, "root"),
    ), signal),
    signal,
  );
}

export async function searchPublicPlaces(
  query: string,
  manifest: PublicManifest,
  signal?: AbortSignal,
): Promise<PublicPlace[]> {
  const prefix = normalizedPrefix(query);
  if (!prefix) return [];
  const shard = manifest.place_prefixes.find((item) => item.prefix === prefix);
  if (!shard) return [];
  const load = async (url: string, requestSignal?: AbortSignal) => {
    const data = await fetchJson<PublicPlaceShard>(url, requestSignal);
    if (data.schema_version !== 1 || data.prefix !== prefix) {
      throw new Error("The place search shard did not match its manifest entry.");
    }
    return data;
  };
  const data = await withCoherentShardFallback(
    (requestSignal) => load(safePath(shard.path, "places"), requestSignal),
    (fallbackManifest) => {
      const fallbackShard = fallbackManifest.place_prefixes.find((item) => item.prefix === prefix);
      if (!fallbackShard) throw new Error("The place shard is missing from the coherent bundled fallback.");
      return load(joinPath(SAME_ORIGIN_DATA_ROOT, dataRelativePath(fallbackShard.path, "places")), signal);
    },
    signal,
  );
  const needle = normalizedSearchKey(query);
  return data.places
    .filter((place) => normalizedSearchKey(place.name).includes(needle))
    .sort((left, right) => {
      const leftStarts = normalizedSearchKey(left.name).startsWith(needle) ? 0 : 1;
      const rightStarts = normalizedSearchKey(right.name).startsWith(needle) ? 0 : 1;
      return leftStarts - rightStarts || left.name.localeCompare(right.name);
    })
    .slice(0, 10);
}

export function containsCoordinate(bounds: PublicBounds, latitude: number, longitude: number): boolean {
  return latitude >= bounds.south && latitude <= bounds.north
    && longitude >= bounds.west && longitude <= bounds.east
    && pointInArizona(latitude, longitude);
}

export function pointInArizona(latitude: number, longitude: number): boolean {
  let inside = false;
  for (let index = 0; index < ARIZONA_STATE_RING.length - 1; index += 1) {
    const start = ARIZONA_STATE_RING[index];
    const end = ARIZONA_STATE_RING[index + 1];
    if (pointOnSegment(longitude, latitude, start, end)) return true;
    const [startLongitude, startLatitude] = start;
    const [endLongitude, endLatitude] = end;
    if ((startLatitude > latitude) === (endLatitude > latitude)) continue;
    const crossingLongitude = startLongitude
      + ((latitude - startLatitude) * (endLongitude - startLongitude) / (endLatitude - startLatitude));
    if (longitude < crossingLongitude) inside = !inside;
  }
  return inside;
}

function pointOnSegment(
  longitude: number,
  latitude: number,
  start: number[],
  end: number[],
): boolean {
  const [startLongitude, startLatitude] = start;
  const [endLongitude, endLatitude] = end;
  const cross = (longitude - startLongitude) * (endLatitude - startLatitude)
    - (latitude - startLatitude) * (endLongitude - startLongitude);
  return Math.abs(cross) <= BOUNDARY_TOLERANCE
    && longitude >= Math.min(startLongitude, endLongitude) - BOUNDARY_TOLERANCE
    && longitude <= Math.max(startLongitude, endLongitude) + BOUNDARY_TOLERANCE
    && latitude >= Math.min(startLatitude, endLatitude) - BOUNDARY_TOLERANCE
    && latitude <= Math.max(startLatitude, endLatitude) + BOUNDARY_TOLERANCE;
}

export function parseArizonaCoordinates(value: string, bounds: PublicBounds): { latitude: number; longitude: number } | null {
  const match = /^\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*$/.exec(value);
  if (!match) return null;
  const latitude = Number(match[1]);
  const longitude = Number(match[2]);
  return Number.isFinite(latitude) && Number.isFinite(longitude) && containsCoordinate(bounds, latitude, longitude)
    ? { latitude, longitude }
    : null;
}
