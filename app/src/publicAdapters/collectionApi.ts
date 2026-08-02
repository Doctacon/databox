import type {
  BirdIdentity,
  BirdWatch,
  CollectionState,
  LifeListEntry,
  ObservationInput,
  PersonalObservation,
  WatchInput,
} from "../types";
import { isPublicSpeciesCode } from "../publicSpeciesCode";
import { publicManifest, randomIdentifier, safeRead, safeWrite } from "./runtime";

const OBSERVATIONS_KEY = "rufous.public.observations.v1";
const WATCHES_KEY = "rufous.public.collection-watches.v1";
const MAX_OBSERVATIONS = 5_000;
const MAX_WATCHES = 100;

function observations(): PersonalObservation[] {
  const rows = safeRead<unknown[]>(OBSERVATIONS_KEY, []);
  return Array.isArray(rows) ? rows.filter((row): row is PersonalObservation => Boolean(
    row && typeof row === "object"
    && typeof (row as PersonalObservation).observation_id === "string"
    && isPublicSpeciesCode((row as PersonalObservation).species_code)
    && /^\d{4}-\d{2}-\d{2}$/.test((row as PersonalObservation).observation_date),
  )).slice(0, MAX_OBSERVATIONS) : [];
}

function watches(): BirdWatch[] {
  const rows = safeRead<unknown[]>(WATCHES_KEY, []);
  return Array.isArray(rows) ? rows.filter((row): row is BirdWatch => Boolean(
    row && typeof row === "object"
    && isPublicSpeciesCode((row as BirdWatch).species_code)
    && typeof (row as BirdWatch).center_latitude === "number"
    && typeof (row as BirdWatch).center_longitude === "number"
    && typeof (row as BirdWatch).active === "boolean",
  )).slice(0, MAX_WATCHES) : [];
}

async function identity(speciesCode: string, previous?: BirdIdentity): Promise<BirdIdentity> {
  if (!isPublicSpeciesCode(speciesCode)) throw new Error("Invalid bird species code.");
  const manifest = await publicManifest();
  const species = manifest.species.find((item) => item.species_code === speciesCode);
  if (!species) return {
    catalog_status: "stale",
    common_name: previous?.common_name ?? null,
    scientific_name: previous?.scientific_name ?? null,
    taxonomic_category: previous?.taxonomic_category ?? null,
  };
  return {
    catalog_status: "current",
    common_name: species.common_name,
    scientific_name: species.scientific_name,
    taxonomic_category: "species",
  };
}

async function currentObservation(row: PersonalObservation): Promise<PersonalObservation> {
  return { ...row, identity: await identity(row.species_code, row.identity) };
}

async function currentWatch(row: BirdWatch): Promise<BirdWatch> {
  return { ...row, identity: await identity(row.species_code, row.identity) };
}

export async function listObservations(): Promise<PersonalObservation[]> {
  return Promise.all(observations()
    .sort((left, right) => right.observation_date.localeCompare(left.observation_date)
      || right.updated_at.localeCompare(left.updated_at))
    .map(currentObservation));
}

export async function listLifeList(): Promise<LifeListEntry[]> {
  const grouped = new Map<string, PersonalObservation[]>();
  for (const row of await listObservations()) grouped.set(row.species_code, [...(grouped.get(row.species_code) ?? []), row]);
  return [...grouped.entries()].map(([speciesCode, rows]) => {
    const dates = rows.map((row) => row.observation_date).sort();
    return {
      species_code: speciesCode,
      first_observed_date: dates[0],
      latest_observed_date: dates.at(-1)!,
      observation_count: rows.length,
      identity: rows[0].identity,
    };
  }).sort((left, right) => (left.identity.common_name ?? left.species_code)
    .localeCompare(right.identity.common_name ?? right.species_code));
}

export async function listWatches(): Promise<BirdWatch[]> {
  return Promise.all(watches().sort((left, right) => right.updated_at.localeCompare(left.updated_at)).map(currentWatch));
}

function validateObservationInput(input: ObservationInput): void {
  if (!isPublicSpeciesCode(input.species_code)
    || !/^\d{4}-\d{2}-\d{2}$/.test(input.observation_date)
    || (input.location !== null && input.location.length > 300)
    || (input.notes !== null && input.notes.length > 2_000)) {
    throw new Error("Check the observation form and try again.");
  }
}

export async function createObservation(input: ObservationInput): Promise<PersonalObservation> {
  validateObservationInput(input);
  const birdIdentity = await identity(input.species_code);
  if (birdIdentity.catalog_status !== "current") throw new Error("That bird is not in the published Arizona catalog.");
  const now = new Date().toISOString();
  const selection = input.location_selection ?? null;
  const row: PersonalObservation = {
    observation_id: randomIdentifier("observation_"),
    species_code: input.species_code,
    observation_date: input.observation_date,
    location: input.location?.trim() || null,
    location_source: selection?.source ?? null,
    location_source_id: selection?.source_id ?? null,
    location_latitude: selection?.latitude ?? null,
    location_longitude: selection?.longitude ?? null,
    location_timezone: selection?.timezone ?? null,
    location_region_code: selection?.region_code ?? null,
    notes: input.notes?.trim() || null,
    created_at: now,
    updated_at: now,
    identity: birdIdentity,
  };
  safeWrite(OBSERVATIONS_KEY, [row, ...observations()].slice(0, MAX_OBSERVATIONS));
  return row;
}

export async function updateObservation(id: string, input: ObservationInput): Promise<PersonalObservation> {
  validateObservationInput(input);
  const rows = observations();
  const index = rows.findIndex((row) => row.observation_id === id);
  if (index < 0) throw new Error("That observation no longer exists in this browser.");
  const birdIdentity = await identity(input.species_code, rows[index].identity);
  if (birdIdentity.catalog_status !== "current") throw new Error("That bird is not in the published Arizona catalog.");
  const selection = input.location_selection ?? null;
  const row: PersonalObservation = {
    ...rows[index],
    species_code: input.species_code,
    observation_date: input.observation_date,
    location: input.location?.trim() || null,
    location_source: selection?.source ?? null,
    location_source_id: selection?.source_id ?? null,
    location_latitude: selection?.latitude ?? null,
    location_longitude: selection?.longitude ?? null,
    location_timezone: selection?.timezone ?? null,
    location_region_code: selection?.region_code ?? null,
    notes: input.notes?.trim() || null,
    updated_at: new Date().toISOString(),
    identity: birdIdentity,
  };
  rows[index] = row;
  safeWrite(OBSERVATIONS_KEY, rows);
  return row;
}

export async function deleteObservation(id: string): Promise<void> {
  const rows = observations();
  const next = rows.filter((row) => row.observation_id !== id);
  if (next.length === rows.length) throw new Error("That observation no longer exists in this browser.");
  safeWrite(OBSERVATIONS_KEY, next);
}

export async function saveWatch(speciesCode: string, input: WatchInput): Promise<BirdWatch> {
  if (!isPublicSpeciesCode(speciesCode)
    || !Number.isFinite(input.radius_miles) || input.radius_miles < 1 || input.radius_miles > 300) {
    throw new Error("Check the watch form and try again.");
  }
  const birdIdentity = await identity(speciesCode);
  if (birdIdentity.catalog_status !== "current") throw new Error("That bird is not in the published Arizona catalog.");
  const rows = watches();
  const existing = rows.find((row) => row.species_code === speciesCode);
  const now = new Date().toISOString();
  const row: BirdWatch = {
    species_code: speciesCode,
    active: existing?.active ?? true,
    center_name: input.center.display_name,
    center_latitude: input.center.latitude,
    center_longitude: input.center.longitude,
    center_timezone: input.center.timezone,
    radius_miles: input.radius_miles,
    activated_at: existing?.activated_at ?? now,
    created_at: existing?.created_at ?? now,
    updated_at: now,
    identity: birdIdentity,
  };
  safeWrite(WATCHES_KEY, [row, ...rows.filter((item) => item.species_code !== speciesCode)].slice(0, MAX_WATCHES));
  return row;
}

export async function setWatchActive(speciesCode: string, active: boolean): Promise<BirdWatch> {
  if (!isPublicSpeciesCode(speciesCode)) throw new Error("Invalid bird species code.");
  const rows = watches();
  const index = rows.findIndex((row) => row.species_code === speciesCode);
  if (index < 0) throw new Error("That watch no longer exists in this browser.");
  const now = new Date().toISOString();
  rows[index] = {
    ...rows[index],
    active,
    activated_at: active ? now : rows[index].activated_at,
    updated_at: now,
    identity: await identity(speciesCode, rows[index].identity),
  };
  safeWrite(WATCHES_KEY, rows);
  return rows[index];
}

export async function deleteWatch(speciesCode: string): Promise<void> {
  if (!isPublicSpeciesCode(speciesCode)) throw new Error("Invalid bird species code.");
  const rows = watches();
  const next = rows.filter((row) => row.species_code !== speciesCode);
  if (next.length === rows.length) throw new Error("That watch no longer exists in this browser.");
  safeWrite(WATCHES_KEY, next);
}

export async function getCollectionState(speciesCode: string): Promise<CollectionState> {
  if (!isPublicSpeciesCode(speciesCode)) throw new Error("Invalid bird species code.");
  const birdIdentity = await identity(speciesCode);
  const observationCount = observations().filter((row) => row.species_code === speciesCode).length;
  const watch = watches().find((row) => row.species_code === speciesCode);
  return {
    species_code: speciesCode,
    catalog_status: birdIdentity.catalog_status,
    observed: observationCount > 0,
    observation_count: observationCount,
    watched: Boolean(watch),
    watch_active: Boolean(watch?.active),
  };
}
