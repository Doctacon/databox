import type {
  BirdIdentity,
  BirdWatch,
  CollectionState,
  LifeListEntry,
  ObservationInput,
  PersonalObservation,
  WatchInput,
} from "./types";

type Row = Record<string, unknown>;

function exact(value: unknown, keys: readonly string[]): Row {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Invalid local collection response");
  const row = value as Row;
  const actual = Object.keys(row).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw new Error("Invalid local collection response");
  }
  return row;
}

function text(value: unknown, max: number, nullable = false): value is string | null {
  return (nullable && value === null) || (typeof value === "string" && value.length > 0 && value.length <= max);
}
function code(value: unknown): value is string { return typeof value === "string" && /^[A-Za-z0-9]{1,64}$/.test(value); }
function date(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1];
}
function timestamp(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 40) return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(?:Z|\+00:00)$/.exec(value);
  if (!match || !date(`${match[1]}-${match[2]}-${match[3]}`)) return false;
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  return hour <= 23 && minute <= 59 && second <= 59 && !Number.isNaN(Date.parse(value));
}
function count(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function finite(value: unknown): value is number { return typeof value === "number" && Number.isFinite(value); }

function identity(value: unknown): BirdIdentity {
  const row = exact(value, ["catalog_status", "common_name", "scientific_name", "taxonomic_category"]);
  if ((row.catalog_status !== "current" && row.catalog_status !== "stale")
    || !text(row.common_name, 200, true) || !text(row.scientific_name, 200, true)
    || (row.taxonomic_category !== null && row.taxonomic_category !== "species" && row.taxonomic_category !== "hybrid")
    || (row.catalog_status === "stale" && (row.common_name !== null || row.scientific_name !== null || row.taxonomic_category !== null))) {
    throw new Error("Invalid local collection response");
  }
  return row as unknown as BirdIdentity;
}

function observation(value: unknown): PersonalObservation {
  const row = exact(value, ["observation_id", "species_code", "observation_date", "location", "notes", "created_at", "updated_at", "identity"]);
  if (!text(row.observation_id, 128) || !code(row.species_code) || !date(row.observation_date)
    || !text(row.location, 300, true) || !text(row.notes, 2000, true)
    || !timestamp(row.created_at) || !timestamp(row.updated_at)
    || Date.parse(row.created_at) > Date.parse(row.updated_at)) throw new Error("Invalid local collection response");
  return { ...(row as unknown as Omit<PersonalObservation, "identity">), identity: identity(row.identity) };
}

function lifeEntry(value: unknown): LifeListEntry {
  const row = exact(value, ["species_code", "first_observed_date", "latest_observed_date", "observation_count", "identity"]);
  if (!code(row.species_code) || !date(row.first_observed_date) || !date(row.latest_observed_date)
    || !count(row.observation_count) || row.observation_count < 1
    || row.first_observed_date > row.latest_observed_date) throw new Error("Invalid local collection response");
  return { ...(row as unknown as Omit<LifeListEntry, "identity">), identity: identity(row.identity) };
}

function watch(value: unknown): BirdWatch {
  const row = exact(value, ["species_code", "active", "center_name", "center_latitude", "center_longitude", "center_timezone", "radius_miles", "activated_at", "created_at", "updated_at", "identity"]);
  if (!code(row.species_code) || typeof row.active !== "boolean" || !text(row.center_name, 300)
    || !finite(row.center_latitude) || row.center_latitude < -90 || row.center_latitude > 90
    || !finite(row.center_longitude) || row.center_longitude < -180 || row.center_longitude > 180
    || !text(row.center_timezone, 64) || !finite(row.radius_miles) || row.radius_miles < 1 || row.radius_miles > 300
    || !timestamp(row.activated_at) || !timestamp(row.created_at) || !timestamp(row.updated_at)
    || Date.parse(row.created_at) > Date.parse(row.updated_at)
    || Date.parse(row.activated_at) > Date.parse(row.updated_at)) {
    throw new Error("Invalid local collection response");
  }
  return { ...(row as unknown as Omit<BirdWatch, "identity">), identity: identity(row.identity) };
}

const safeErrors: Record<string, string> = {
  collection_busy: "Another collection change is in progress. Try again shortly.",
  database_busy: "The warehouse is refreshing. Try again shortly.",
  database_unavailable: "The local collection is unavailable.",
  species_not_found: "That bird is not in the current Arizona catalog.",
  not_found: "That collection item no longer exists.",
  invalid_location: "Select a location inside Arizona.",
  invalid_request: "Check the collection form and try again.",
  confirmation_required: "Confirm permanent deletion before continuing.",
};

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
  });
  let body: unknown;
  try { body = await response.json(); }
  catch { throw new Error("The local collection is unavailable."); }
  if (!response.ok) {
    try {
      const outer = exact(body, ["error"]);
      const error = exact(outer.error, ["code", "message"]);
      if (typeof error.code === "string" && typeof error.message === "string" && safeErrors[error.code]) {
        throw new Error(safeErrors[error.code]);
      }
    } catch (reason) {
      if (reason instanceof Error && reason.message !== "Invalid local collection response") throw reason;
    }
    throw new Error("The local collection is unavailable.");
  }
  return body;
}

function boundedList(value: unknown, key: string): unknown[] {
  const row = exact(value, [key]);
  const rows = row[key];
  if (!Array.isArray(rows) || rows.length > 10000) throw new Error("Invalid local collection response");
  return rows;
}

export async function listObservations(): Promise<PersonalObservation[]> {
  return boundedList(await request("/api/observations"), "observations").map(observation);
}
export async function listLifeList(): Promise<LifeListEntry[]> {
  return boundedList(await request("/api/life-list"), "birds").map(lifeEntry);
}
export async function listWatches(): Promise<BirdWatch[]> {
  return boundedList(await request("/api/watches"), "watches").map(watch);
}
export async function createObservation(input: ObservationInput): Promise<PersonalObservation> {
  return observation(await request("/api/observations", { method: "POST", body: JSON.stringify(input) }));
}
export async function updateObservation(id: string, input: ObservationInput): Promise<PersonalObservation> {
  return observation(await request(`/api/observations/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(input) }));
}
export async function deleteObservation(id: string): Promise<void> {
  const row = exact(await request(`/api/observations/${encodeURIComponent(id)}?confirm=true`, { method: "DELETE" }), ["removed"]);
  if (row.removed !== true) throw new Error("Invalid local collection response");
}
export async function saveWatch(speciesCode: string, input: WatchInput): Promise<BirdWatch> {
  const center = input.center;
  return watch(await request(`/api/watches/${encodeURIComponent(speciesCode)}`, {
    method: "PUT",
    body: JSON.stringify({
      ...input,
      center: {
        display_name: center.display_name,
        latitude: center.latitude,
        longitude: center.longitude,
        timezone: center.timezone,
        region_code: center.region_code,
      },
    }),
  }));
}
export async function setWatchActive(speciesCode: string, active: boolean): Promise<BirdWatch> {
  return watch(await request(`/api/watches/${encodeURIComponent(speciesCode)}/${active ? "resume" : "pause"}`, { method: "POST" }));
}
export async function deleteWatch(speciesCode: string): Promise<void> {
  const row = exact(await request(`/api/watches/${encodeURIComponent(speciesCode)}`, { method: "DELETE" }), ["removed"]);
  if (row.removed !== true) throw new Error("Invalid local collection response");
}
export async function getCollectionState(speciesCode: string): Promise<CollectionState> {
  const row = exact(await request(`/api/birds/${encodeURIComponent(speciesCode)}/collection-state`), ["species_code", "catalog_status", "observed", "observation_count", "watched", "watch_active"]);
  if (!code(row.species_code) || row.species_code !== speciesCode
    || (row.catalog_status !== "current" && row.catalog_status !== "stale")
    || typeof row.observed !== "boolean" || !count(row.observation_count)
    || row.observed !== (row.observation_count > 0)
    || typeof row.watched !== "boolean" || typeof row.watch_active !== "boolean"
    || (row.watch_active && !row.watched)) {
    throw new Error("Invalid local collection response");
  }
  return row as unknown as CollectionState;
}
