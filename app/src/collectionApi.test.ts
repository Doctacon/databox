import { afterEach, describe, expect, it, vi } from "vitest";
import { getCollectionState, listLifeList, listObservations, listWatches, listWishlist } from "./collectionApi";

function response(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } }));
}

const currentIdentity = {
  catalog_status: "current",
  common_name: "Arizona Bird",
  scientific_name: "Avis arizonae",
  taxonomic_category: "species",
};
const observation = {
  observation_id: "obs-1",
  species_code: "bird001",
  observation_date: "2024-02-29",
  location: null,
  notes: null,
  created_at: "2026-07-10T01:02:03.123456Z",
  updated_at: "2026-07-10T01:02:04+00:00",
  identity: currentIdentity,
};

async function rejects(body: unknown, call: () => Promise<unknown>) {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response(body));
  await expect(call()).rejects.toThrow("Invalid local collection response");
  vi.restoreAllMocks();
}

afterEach(() => vi.restoreAllMocks());

describe("strict collection response validation", () => {
  it("accepts leap-day dates and bounded UTC timestamps", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ observations: [observation] }));
    await expect(listObservations()).resolves.toHaveLength(1);
  });

  it.each([
    { observation_date: "2026-02-29" },
    { observation_date: "2024-13-01" },
    { observation_date: "2024-04-31" },
    { created_at: "2026-07-10T01:02:03" },
    { created_at: "2026-07-10T01:02:03-07:00" },
    { created_at: "2026-07-10T24:00:00Z" },
    { created_at: "2026-07-10T01:02:03.1234567Z" },
    { created_at: "2026-07-10T01:02:05Z", updated_at: "2026-07-10T01:02:04Z" },
  ])("rejects invalid date/timestamp row %#", async (change) => {
    await rejects({ observations: [{ ...observation, ...change }] }, listObservations);
  });

  it("rejects unsafe counts and reversed life-list dates", async () => {
    const entry = {
      species_code: "bird001", first_observed_date: "2026-07-10", latest_observed_date: "2026-07-09",
      observation_count: 1, identity: currentIdentity,
    };
    await rejects({ birds: [entry] }, listLifeList);
    await rejects({ birds: [{ ...entry, first_observed_date: "2026-07-09", observation_count: Number.MAX_SAFE_INTEGER + 1 }] }, listLifeList);
  });

  it.each([
    { observed: false, observation_count: 1, wishlisted: false, watched: false, watch_active: false },
    { observed: true, observation_count: 0, wishlisted: false, watched: false, watch_active: false },
    { observed: false, observation_count: 0, wishlisted: false, watched: false, watch_active: true },
  ])("rejects inconsistent collection state %#", async (state) => {
    await rejects({ species_code: "bird001", catalog_status: "current", ...state }, () => getCollectionState("bird001"));
  });

  it("accepts independent wishlist state and a paused watch", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({
      species_code: "bird001", catalog_status: "current", observed: false, observation_count: 0,
      wishlisted: true, watched: true, watch_active: false,
    }));
    await expect(getCollectionState("bird001")).resolves.toMatchObject({ wishlisted: true, watched: true, watch_active: false });
  });

  it("rejects collection state for a different requested species", async () => {
    await rejects({
      species_code: "bird002", catalog_status: "current", observed: false, observation_count: 0,
      wishlisted: false, watched: false, watch_active: false,
    }, () => getCollectionState("bird001"));
  });

  it("requires stale identities to omit current catalog metadata", async () => {
    await rejects({ birds: [{ species_code: "bird001", created_at: "2026-07-10T01:00:00Z", identity: { ...currentIdentity, catalog_status: "stale" } }] }, listWishlist);
  });

  it("rejects watch timestamp ordering and malformed UTC timestamps", async () => {
    const watch = {
      species_code: "bird001", active: true, center_name: "Prescott", center_latitude: 34.5,
      center_longitude: -112.4, center_timezone: "America/Phoenix", radius_miles: 25,
      activated_at: "2026-07-10T02:00:00Z", created_at: "2026-07-10T01:00:00Z",
      updated_at: "2026-07-10T01:30:00Z", identity: currentIdentity,
    };
    await rejects({ watches: [watch] }, listWatches);
  });
});
