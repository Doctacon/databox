import { getPublicCell } from "./publicData";
import type { PublicBounds, PublicManifest, PublicWatch, WatchEvaluation, WatchMatch } from "./publicTypes";

export const PUBLIC_WATCH_STORAGE_KEY = "rufous.public.watches.v1";
const MAX_WATCHES = 25;

export function distanceMiles(
  firstLatitude: number,
  firstLongitude: number,
  secondLatitude: number,
  secondLongitude: number,
): number {
  const radians = (degrees: number) => degrees * Math.PI / 180;
  const latitudeDelta = radians(secondLatitude - firstLatitude);
  const longitudeDelta = radians(secondLongitude - firstLongitude);
  const a = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(radians(firstLatitude)) * Math.cos(radians(secondLatitude))
    * Math.sin(longitudeDelta / 2) ** 2;
  return 3958.7613 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function cellIntersectsRadius(
  bounds: PublicBounds,
  latitude: number,
  longitude: number,
  radiusMiles: number,
): boolean {
  const nearestLatitude = Math.max(bounds.south, Math.min(latitude, bounds.north));
  const nearestLongitude = Math.max(bounds.west, Math.min(longitude, bounds.east));
  return distanceMiles(latitude, longitude, nearestLatitude, nearestLongitude) <= radiusMiles;
}

export async function evaluatePublicWatch(
  watch: PublicWatch,
  manifest: PublicManifest,
  signal?: AbortSignal,
): Promise<WatchEvaluation> {
  const cells = manifest.cells.filter((cell) => cellIntersectsRadius(
    cell.bounds,
    watch.center_latitude,
    watch.center_longitude,
    watch.radius_miles,
  ));
  const loaded = await Promise.all(cells.map((cell) => getPublicCell(cell.path, signal)));
  const matches: WatchMatch[] = loaded.flatMap((cell) => cell.observations)
    .filter((observation) => observation.species_code === watch.species_code)
    .map((observation) => ({
      ...observation,
      distance_miles: distanceMiles(
        watch.center_latitude,
        watch.center_longitude,
        observation.location.latitude,
        observation.location.longitude,
      ),
    }))
    .filter((observation) => observation.distance_miles <= watch.radius_miles)
    .sort((left, right) => Date.parse(right.observed_at) - Date.parse(left.observed_at)
      || left.distance_miles - right.distance_miles);
  return {
    watch,
    matches,
    evaluated_at: new Date().toISOString(),
    loaded_cell_ids: loaded.map((cell) => cell.cell_id),
  };
}

function validWatch(value: unknown): value is PublicWatch {
  if (!value || typeof value !== "object") return false;
  const watch = value as Partial<PublicWatch>;
  return typeof watch.id === "string" && watch.id.length <= 100
    && typeof watch.species_code === "string" && /^[a-z0-9_-]+$/i.test(watch.species_code)
    && typeof watch.bird_name === "string"
    && typeof watch.center_name === "string"
    && typeof watch.center_latitude === "number" && Number.isFinite(watch.center_latitude)
    && typeof watch.center_longitude === "number" && Number.isFinite(watch.center_longitude)
    && (watch.center_timezone === "America/Phoenix" || watch.center_timezone === "America/Denver")
    && typeof watch.radius_miles === "number" && watch.radius_miles >= 1 && watch.radius_miles <= 300
    && typeof watch.outing_date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(watch.outing_date)
    && typeof watch.created_at === "string";
}

export function readPublicWatches(storage: Pick<Storage, "getItem"> = window.localStorage): PublicWatch[] {
  try {
    const parsed: unknown = JSON.parse(storage.getItem(PUBLIC_WATCH_STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(validWatch).slice(0, MAX_WATCHES) : [];
  } catch {
    return [];
  }
}

export function writePublicWatches(
  watches: PublicWatch[],
  storage: Pick<Storage, "setItem"> = window.localStorage,
): void {
  storage.setItem(PUBLIC_WATCH_STORAGE_KEY, JSON.stringify(watches.filter(validWatch).slice(0, MAX_WATCHES)));
}

export function createWatchId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `watch-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
