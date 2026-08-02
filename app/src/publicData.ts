import type {
  PublicAttribution,
  PublicBounds,
  PublicCell,
  PublicManifest,
  PublicPlace,
  PublicPlaceShard,
  PublicSpeciesProfile,
  PublicSpeciesSummary,
} from "./publicTypes";
import arizonaBoundariesRaw from "./assets/arizona-boundaries.geojson?raw";

const DATA_ROOT = "/data";
const SAFE_SEGMENT = /^[a-z0-9_-]+$/i;
const BOUNDARY_TOLERANCE = 1e-9;
const EBIRD_EOD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e";
const RUFOUS_TAXON_KEY = 2476855;

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

function safePath(path: string, expectedPrefix: string): string {
  if (!path.startsWith(expectedPrefix) || path.includes("..") || !path.endsWith(".json")) {
    throw new Error("The public data manifest contains an invalid shard path.");
  }
  return path;
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

export async function getPublicManifest(signal?: AbortSignal): Promise<PublicManifest> {
  const manifest = await fetchJson<PublicManifest>(`${DATA_ROOT}/manifest.json`, signal);
  const expectedOccurrenceSource = manifest.release_mode === "production" ? "gbif" : "synthetic";
  const expectedDatasetKey = manifest.release_mode === "production" ? EBIRD_EOD_DATASET_KEY : null;
  const expectedCoverage = manifest.release_mode === "production" ? "bounded_sample" : "fictional_fixture";
  const expectedRequiredTaxon = manifest.release_mode === "production" ? RUFOUS_TAXON_KEY : null;
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
    || manifest.license_policy?.version !== 1
    || !Number.isInteger(manifest.counts?.attribution_items)
  ) {
    throw new Error("This Rufous public data release is not supported.");
  }
  return manifest;
}

export async function getPublicSpecies(
  species: PublicSpeciesSummary,
  signal?: AbortSignal,
): Promise<PublicSpeciesProfile> {
  if (!SAFE_SEGMENT.test(species.species_code)) throw new Error("Invalid species code.");
  const path = safePath(species.profile_path, `${DATA_ROOT}/species/`);
  const profile = await fetchJson<PublicSpeciesProfile>(path, signal);
  if (profile.schema_version !== 1 || profile.species_code !== species.species_code) {
    throw new Error("The bird profile did not match the public catalog.");
  }
  return profile;
}

export async function getPublicCell(path: string, signal?: AbortSignal): Promise<PublicCell> {
  return fetchJson<PublicCell>(safePath(path, `${DATA_ROOT}/cells/`), signal);
}

export async function getPublicAttribution(path: string, signal?: AbortSignal): Promise<PublicAttribution> {
  return fetchJson<PublicAttribution>(safePath(path, `${DATA_ROOT}/`), signal);
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
  const data = await fetchJson<PublicPlaceShard>(safePath(shard.path, `${DATA_ROOT}/places/`), signal);
  if (data.schema_version !== 1 || data.prefix !== prefix) {
    throw new Error("The place search shard did not match its manifest entry.");
  }
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
