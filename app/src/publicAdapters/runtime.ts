import { getPublicCell, getPublicManifest, getPublicSpecies } from "../publicData";
import { isPublicSpeciesCode } from "../publicSpeciesCode";
import { distanceMiles } from "../publicWatch";
import type { PublicCellSummary, PublicManifest, PublicObservation, PublicSpeciesProfile } from "../publicTypes";

let manifestPromise: Promise<PublicManifest> | null = null;
const profilePromises = new Map<string, Promise<PublicSpeciesProfile>>();
const cellPromises = new Map<string, Promise<PublicObservation[]>>();

export function publicManifest(): Promise<PublicManifest> {
  if (!manifestPromise) {
    const pending = getPublicManifest().catch((reason: unknown) => {
      if (manifestPromise === pending) manifestPromise = null;
      throw reason;
    });
    manifestPromise = pending;
  }
  return manifestPromise;
}

export async function publicProfile(speciesCode: string): Promise<PublicSpeciesProfile> {
  if (!isPublicSpeciesCode(speciesCode)) throw new Error("Invalid bird species code.");
  const manifest = await publicManifest();
  const species = manifest.species.find((item) => item.species_code === speciesCode);
  if (!species) throw new Error("Bird not found in the published Arizona catalog.");
  let pending = profilePromises.get(speciesCode);
  if (!pending) {
    pending = getPublicSpecies(species).catch((reason: unknown) => {
      profilePromises.delete(speciesCode);
      throw reason;
    });
    profilePromises.set(speciesCode, pending);
  }
  return pending;
}

function cellObservations(cell: PublicCellSummary): Promise<PublicObservation[]> {
  let pending = cellPromises.get(cell.cell_id);
  if (!pending) {
    pending = getPublicCell(cell.path).then((data) => {
      if (data.schema_version !== 1 || data.cell_id !== cell.cell_id) {
        throw new Error("A published observation shard did not match its manifest entry.");
      }
      return data.observations;
    }).catch((reason: unknown) => {
      cellPromises.delete(cell.cell_id);
      throw reason;
    });
    cellPromises.set(cell.cell_id, pending);
  }
  return pending;
}

function cellIntersectsRadius(
  cell: PublicCellSummary,
  latitude: number,
  longitude: number,
  radiusMiles: number,
): boolean {
  const nearestLatitude = Math.max(cell.bounds.south, Math.min(latitude, cell.bounds.north));
  const nearestLongitude = Math.max(cell.bounds.west, Math.min(longitude, cell.bounds.east));
  return distanceMiles(latitude, longitude, nearestLatitude, nearestLongitude) <= radiusMiles;
}

export async function publicObservations(options: {
  speciesCode?: string;
  center?: { latitude: number; longitude: number; radiusMiles: number };
} = {}): Promise<PublicObservation[]> {
  if (options.speciesCode !== undefined && !isPublicSpeciesCode(options.speciesCode)) {
    throw new Error("Invalid bird species code.");
  }
  const manifest = await publicManifest();
  const cells = options.center
    ? manifest.cells.filter((cell) => cellIntersectsRadius(
      cell,
      options.center!.latitude,
      options.center!.longitude,
      options.center!.radiusMiles,
    ))
    : manifest.cells;
  const observations = (await Promise.all(cells.map(cellObservations))).flat();
  return options.speciesCode
    ? observations.filter((item) => item.species_code === options.speciesCode)
    : observations;
}

export function randomIdentifier(prefix: string): string {
  if (typeof crypto.randomUUID === "function") return `${prefix}${crypto.randomUUID().replaceAll("-", "")}`;
  const bytes = new Uint8Array(16);
  if (typeof crypto.getRandomValues === "function") crypto.getRandomValues(bytes);
  else bytes.forEach((_, index) => { bytes[index] = Math.floor(Math.random() * 256); });
  return `${prefix}${Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
}

export function localDateTimeIso(value: string, timeZone: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(value);
  if (!match) throw new Error("Choose a valid outing date and time.");
  const desired = Date.UTC(
    Number(match[1]), Number(match[2]) - 1, Number(match[3]),
    Number(match[4]), Number(match[5]), Number(match[6] || 0),
  );
  let instant = desired;
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hourCycle: "h23",
  });
  for (let iteration = 0; iteration < 3; iteration += 1) {
    const parts = formatter.formatToParts(new Date(instant));
    const get = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((part) => part.type === type)?.value);
    const displayed = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second"));
    instant -= displayed - desired;
  }
  return new Date(instant).toISOString();
}

export function safeRead<T>(key: string, fallback: T): T {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(key) ?? "null");
    return value === null ? fallback : value as T;
  } catch {
    return fallback;
  }
}

export function safeWrite(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    throw new Error("This browser could not save Rufous data. Check private-browsing or storage settings.");
  }
}

export function resetPublicRuntimeForTests(): void {
  manifestPromise = null;
  profilePromises.clear();
  cellPromises.clear();
}
