import { afterEach, describe, expect, it, vi } from "vitest";
import { getMapSnapshot } from "./mapApi";

function response(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

const encounter = {
  source_observation_id: "S1", species_code: "abc123",
  common_name: "Alpha Bird", scientific_name: "Avis alpha",
  family_common_name: "Fixture Birds", family_scientific_name: "Fixtureidae",
  observation_at: "2026-07-09T08:30:00", observation_count: 2, notable: true,
  location_id: "L1", location_name: "Trail (private)", latitude: 34.54,
  longitude: -112.47, access_warning: true,
};
const unavailablePhoto = { status: "unavailable", source_record_id: null, species_name: null, display_url: null, source_url: null, creator: null, rights_holder: null, publisher: null, format: null, license_text: null, license_url: null, selection_reason: null, provider: null, license_code: null, original_width: null, original_height: null, caveats: [], lookup_at: null };
const snapshot = {
  snapshot_latest_observation_at: encounter.observation_at,
  source_freshness_at: "2026-07-09T13:00:00",
  encounters: [encounter],
  photos: [{ species_code: encounter.species_code, scientific_name: encounter.scientific_name, photo: unavailablePhoto }],
};

afterEach(() => vi.restoreAllMocks());

describe("Field Map snapshot browser contract", () => {
  it("accepts only the exact bounded snapshot and requests the local GET", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() => response(snapshot));
    await expect(getMapSnapshot()).resolves.toEqual(snapshot);
    expect(fetchMock).toHaveBeenCalledWith("/api/map-snapshot", { headers: { "Content-Type": "application/json" } });
  });

  it.each([
    ["extra snapshot key", { ...snapshot, private_notes: "leak" }],
    ["extra encounter key", { ...snapshot, encounters: [{ ...encounter, payload: {} }] }],
    ["duplicate", { ...snapshot, encounters: [encounter, encounter] }],
    ["wrong latest", { ...snapshot, snapshot_latest_observation_at: "2026-07-08T08:30:00" }],
    ["missing identity", { ...snapshot, encounters: [{ ...encounter, common_name: null, scientific_name: null }] }],
    ["missing family", { ...snapshot, encounters: [{ ...encounter, family_common_name: null, family_scientific_name: null }] }],
    ["blank location", { ...snapshot, encounters: [{ ...encounter, location_name: " " }] }],
    ["non-finite coordinate", { ...snapshot, encounters: [{ ...encounter, latitude: Number.POSITIVE_INFINITY }] }],
    ["out-of-bounds coordinate", { ...snapshot, encounters: [{ ...encounter, latitude: 12 }] }],
    ["count zero", { ...snapshot, encounters: [{ ...encounter, observation_count: 0 }] }],
    ["coerced boolean", { ...snapshot, encounters: [{ ...encounter, notable: 1 }] }],
    ["warning mismatch", { ...snapshot, encounters: [{ ...encounter, access_warning: false }] }],
    ["missing freshness", { ...snapshot, source_freshness_at: null }],
  ])("rejects %s", async (_name, attack) => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(attack));
    await expect(getMapSnapshot()).rejects.toThrow("Invalid Field Map response");
  });

  it("accepts a coherent empty snapshot", async () => {
    const empty = { snapshot_latest_observation_at: null, source_freshness_at: null, encounters: [], photos: [] };
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(empty));
    await expect(getMapSnapshot()).resolves.toEqual(empty);
  });

  it("rejects over 10,000 encounters instead of truncating", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({
      ...snapshot,
      encounters: Array.from({ length: 10001 }, (_, index) => ({
        ...encounter, source_observation_id: `S${index}`,
      })),
    }));
    await expect(getMapSnapshot()).rejects.toThrow("Invalid Field Map response");
  });

  it("allows only exact safe local errors", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({
      error: { code: "database_busy", message: "The warehouse is refreshing; try again shortly" },
    }, 503)).mockImplementationOnce(() => response({
      error: { code: "database_unavailable", message: "raw database details" },
    }, 503));
    await expect(getMapSnapshot()).rejects.toThrow("The warehouse is refreshing; try again shortly");
    await expect(getMapSnapshot()).rejects.toThrow("The local Field Map is unavailable");
  });
});
