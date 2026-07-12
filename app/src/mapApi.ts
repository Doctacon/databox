import { isoTimestampMicros, isIsoTimestamp } from "./isoDateTime";
import type { MapEncounter, MapSnapshot } from "./types";

type Row = Record<string, unknown>;

const encounterKeys = [
  "source_observation_id", "species_code", "common_name", "scientific_name",
  "family_common_name", "family_scientific_name", "observation_at", "observation_count",
  "notable", "location_id", "location_name", "latitude", "longitude", "access_warning",
] as const;

function exact(value: unknown, keys: readonly string[]): Row {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Invalid Field Map response");
  const row = value as Row;
  const actual = Object.keys(row).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw new Error("Invalid Field Map response");
  }
  return row;
}

function safeText(value: unknown, max: number, nullable = false): value is string | null {
  return value === null ? nullable : typeof value === "string" && value.length > 0
    && value.length <= max && value.trim().length > 0 && !/[\u0000-\u001f\u007f]/.test(value);
}

function encounter(value: unknown): MapEncounter {
  const row = exact(value, encounterKeys);
  if (typeof row.source_observation_id !== "string" || !/^[A-Za-z0-9_-]{1,64}$/.test(row.source_observation_id)
    || typeof row.species_code !== "string" || !/^[A-Za-z0-9]{1,64}$/.test(row.species_code)
    || !safeText(row.common_name, 200, true) || !safeText(row.scientific_name, 200, true)
    || (row.common_name === null && row.scientific_name === null)
    || !safeText(row.family_common_name, 200, true) || !safeText(row.family_scientific_name, 200, true)
    || (row.family_common_name === null && row.family_scientific_name === null)
    || !isIsoTimestamp(row.observation_at)
    || typeof row.observation_count !== "number" || !Number.isInteger(row.observation_count)
    || row.observation_count < 1 || row.observation_count > 1_000_000
    || typeof row.notable !== "boolean"
    || typeof row.location_id !== "string" || !/^[A-Za-z0-9_-]{1,64}$/.test(row.location_id)
    || !safeText(row.location_name, 300)
    || typeof row.latitude !== "number" || !Number.isFinite(row.latitude)
    || row.latitude < 31.3 || row.latitude > 37.1
    || typeof row.longitude !== "number" || !Number.isFinite(row.longitude)
    || row.longitude < -114.9 || row.longitude > -109
    || typeof row.access_warning !== "boolean"
    || row.access_warning !== /\(private\)/i.test(row.location_name as string)) {
    throw new Error("Invalid Field Map response");
  }
  return row as unknown as MapEncounter;
}

function safeError(status: number, value: unknown): string {
  try {
    const wrapper = exact(value, ["error"]);
    const error = exact(wrapper.error, ["code", "message"]);
    if (status === 503 && error.code === "database_busy"
      && error.message === "The warehouse is refreshing; try again shortly") return error.message;
    if (status === 503 && error.code === "database_unavailable"
      && error.message === "The local Field Map is unavailable") return error.message;
  } catch {
    // Use the bounded fallback below.
  }
  return "The local Field Map is unavailable";
}

export async function getMapSnapshot(): Promise<MapSnapshot> {
  const response = await fetch("/api/map-snapshot", { headers: { "Content-Type": "application/json" } });
  let body: unknown;
  try { body = await response.json(); } catch { throw new Error("The local Field Map is unavailable"); }
  if (!response.ok) throw new Error(safeError(response.status, body));
  const row = exact(body, ["snapshot_latest_observation_at", "source_freshness_at", "encounters"]);
  if (!isIsoTimestamp(row.snapshot_latest_observation_at, true)
    || !isIsoTimestamp(row.source_freshness_at, true)
    || !Array.isArray(row.encounters) || row.encounters.length > 10_000) {
    throw new Error("Invalid Field Map response");
  }
  const encounters = row.encounters.map(encounter);
  const identifiers = encounters.map((item) => item.source_observation_id);
  const latest = encounters.reduce<bigint | null>((current, item) => {
    const value = isoTimestampMicros(item.observation_at)!;
    return current === null || value > current ? value : current;
  }, null);
  if (new Set(identifiers).size !== identifiers.length
    || (encounters.length > 0 && row.source_freshness_at === null)
    || (row.snapshot_latest_observation_at === null ? latest !== null
      : isoTimestampMicros(row.snapshot_latest_observation_at) !== latest)) {
    throw new Error("Invalid Field Map response");
  }
  return { ...row, encounters } as MapSnapshot;
}
