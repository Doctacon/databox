import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import manifest from "../../public/data/manifest.json";
import gilwoo from "../../public/data/species/gilwoo.json";
import mexjay from "../../public/data/species/mexjay.json";
import rufhum from "../../public/data/species/rufhum.json";
import n32w111 from "../../public/data/cells/n32w111.json";
import n33w113 from "../../public/data/cells/n33w113.json";
import n34w113 from "../../public/data/cells/n34w113.json";
import prescott from "../../public/data/places/pr.json";
import { getBird } from "./birdApi";
import { createObservation, getCollectionState, listLifeList, saveWatch } from "./collectionApi";
import { getMapSnapshot } from "./mapApi";
import { resetPublicRuntimeForTests } from "./runtime";
import { createTargetPlan } from "./targetApi";
import { createPlan, listPlans, searchLocations } from "./tripApi";
import { TripCalendarControls } from "./TripCalendarControls";
import { evaluateBrowserWatch } from "./watchEvaluation";

function json(value: unknown): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } }));
}

function mockFixtureFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    const fixtures: Record<string, unknown> = {
      "/data/manifest.json": manifest,
      "/data/species/gilwoo.json": gilwoo,
      "/data/species/mexjay.json": mexjay,
      "/data/species/rufhum.json": rufhum,
      "/data/cells/n32w111.json": n32w111,
      "/data/cells/n33w113.json": n33w113,
      "/data/cells/n34w113.json": n34w113,
      "/data/places/pr.json": prescott,
    };
    return url in fixtures ? json(fixtures[url]) : Promise.resolve(new Response("not found", { status: 404 }));
  });
}

const PRODUCTION_SPECIES_CODE = "gbif-2476855";

function mockProductionFixtureFetch() {
  const productionManifest = {
    ...structuredClone(manifest),
    release_mode: "production",
    source_policy: {
      direct_ebird: "excluded",
      occurrence_source: "gbif",
      gbif_dataset_key: "4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
      coverage: "bounded_sample",
      required_taxon_key: 2476855,
    },
    counts: { ...manifest.counts, species: 1, observations: 1 },
    species: [{
      species_code: PRODUCTION_SPECIES_CODE,
      common_name: "Rufous Hummingbird",
      scientific_name: "Selasphorus rufus",
      profile_path: `/data/species/${PRODUCTION_SPECIES_CODE}.json`,
    }],
    cells: [{ ...n34w113, path: "/data/cells/n34w113.json", observation_count: 1, observations: undefined }],
  };
  const productionProfile = { ...structuredClone(rufhum), species_code: PRODUCTION_SPECIES_CODE };
  const productionCell = {
    ...structuredClone(n34w113),
    observations: [{
      ...structuredClone(n34w113.observations[1]),
      public_id: "gbif-generalized-rufous-fixture",
      species_code: PRODUCTION_SPECIES_CODE,
      source: "gbif",
    }],
  };
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const fixtures: Record<string, unknown> = {
      "/data/manifest.json": productionManifest,
      [`/data/species/${PRODUCTION_SPECIES_CODE}.json`]: productionProfile,
      "/data/cells/n34w113.json": productionCell,
      "/data/places/pr.json": prescott,
    };
    const url = String(input);
    return url in fixtures ? json(fixtures[url]) : Promise.resolve(new Response("not found", { status: 404 }));
  });
}

beforeEach(() => {
  localStorage.clear();
  resetPublicRuntimeForTests();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("full public-app browser adapters", () => {
  it("searches GNIS shards and asks coordinate users to choose a time convention", async () => {
    mockFixtureFetch();
    const places = await searchLocations("Prescott");
    const coordinates = await searchLocations("34.54,-112.47");

    expect(places).toMatchObject([{ display_name: "Prescott, Arizona", source: "usgs_gnis", timezone: "America/Phoenix" }]);
    expect(coordinates.map((item) => item.timezone)).toEqual(["America/Phoenix", "America/Denver"]);
    expect(coordinates.every((item) => item.source === "manual_coordinates")).toBe(true);
  });

  it("builds and saves deterministic trip and target plans from licensed static evidence", async () => {
    mockFixtureFetch();
    const [location] = await searchLocations("Prescott");
    const trip = await createPlan({
      location: location.display_name,
      location_selection: location,
      start_at: "2026-08-10T06:30",
      duration_minutes: 120,
      skill_level: "intermediate",
    });
    const target = await createTargetPlan({
      species_code: "rufhum",
      location: location.display_name,
      location_selection: location,
      radius_miles: 100,
      start_at: "2026-08-10T06:30",
      duration_minutes: 120,
    });

    expect(trip.recommendations.length).toBeGreaterThan(0);
    expect(trip.recommendations.every((item) => item.recommendation_group === "gbif_context")).toBe(true);
    expect(trip.tool_traces.map((item) => item.tool_name)).toEqual([
      "lookup_recent_observation_evidence",
      "lookup_gbif_occurrence_evidence",
      "compose_deterministic_field_plan",
    ]);
    expect(trip.weather).toBeNull();
    expect(await listPlans()).toHaveLength(1);
    expect(target.target_plan_id).toMatch(/^target_[0-9a-f]{32}$/);
    expect(target.weather.status).toBe("unavailable");
    expect(target.candidates.length).toBeGreaterThan(0);
    expect(target.caveats.join(" ")).toMatch(/No AI model, email service, or private observation/);
  });

  it("keeps observations, life list, and watches in browser storage", async () => {
    mockFixtureFetch();
    const [location] = await searchLocations("Prescott");
    await createObservation({
      species_code: "mexjay",
      observation_date: "2026-08-01",
      location: location.display_name,
      location_selection: location,
      notes: "Heard near oaks.",
    });
    const watch = await saveWatch("mexjay", { center: location, radius_miles: 25 });
    const evaluation = await evaluateBrowserWatch(watch);

    expect(await listLifeList()).toMatchObject([{ species_code: "mexjay", observation_count: 1 }]);
    expect(await getCollectionState("mexjay")).toEqual({
      species_code: "mexjay",
      catalog_status: "current",
      observed: true,
      observation_count: 1,
      watched: true,
      watch_active: true,
    });
    expect(localStorage.getItem("rufous.public.observations.v1")).toContain("Heard near oaks");
    expect(evaluation).toMatchObject({ species_code: "mexjay", match_count: 1, nearest_location_name: "Synthetic Granite Trail Site" });
  });

  it("supports production gbif taxon codes through profiles, targets, observations, and watches", async () => {
    mockProductionFixtureFetch();
    const profile = await getBird(PRODUCTION_SPECIES_CODE);
    const [location] = await searchLocations("Prescott");
    const target = await createTargetPlan({
      species_code: PRODUCTION_SPECIES_CODE,
      location: location.display_name,
      location_selection: location,
      radius_miles: 100,
      start_at: "2026-08-10T06:30",
      duration_minutes: 120,
    });
    await createObservation({
      species_code: PRODUCTION_SPECIES_CODE,
      observation_date: "2026-08-01",
      location: location.display_name,
      location_selection: location,
      notes: null,
    });
    const watch = await saveWatch(PRODUCTION_SPECIES_CODE, { center: location, radius_miles: 25 });
    const evaluation = await evaluateBrowserWatch(watch);

    expect(profile).toMatchObject({ species_code: PRODUCTION_SPECIES_CODE, common_name: "Rufous Hummingbird" });
    expect(target).toMatchObject({ species_code: PRODUCTION_SPECIES_CODE });
    expect(target.candidates).toHaveLength(1);
    expect(await listLifeList()).toMatchObject([{ species_code: PRODUCTION_SPECIES_CODE, observation_count: 1 }]);
    expect(await getCollectionState(PRODUCTION_SPECIES_CODE)).toMatchObject({ observed: true, watched: true, watch_active: true });
    expect(evaluation).toMatchObject({ species_code: PRODUCTION_SPECIES_CODE, match_count: 1 });
  });

  it("maps all published cells and downloads a publish-only calendar file", async () => {
    mockFixtureFetch();
    const snapshot = await getMapSnapshot();
    expect(snapshot.encounters).toHaveLength(6);
    expect(snapshot.encounters.every((item) => item.access_warning === false)).toBe(true);

    const [location] = await searchLocations("Prescott");
    const trip = await createPlan({
      location: location.display_name,
      location_selection: location,
      start_at: "2026-08-10T06:30",
      duration_minutes: 90,
    });
    let clicked: HTMLAnchorElement | null = null;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function capture(this: HTMLAnchorElement) { clicked = this; });
    render(<TripCalendarControls planId={trip.plan.trip_plan_id} invite={trip.calendar_invite} onChange={() => undefined} />);
    await userEvent.click(screen.getByRole("button", { name: "Download calendar event (.ics)" }));

    expect(await screen.findByText(/did not collect an email address/)).toBeVisible();
    expect(clicked).not.toBeNull();
    expect(clicked!.download).toMatch(/^rufous-prescott-arizona\.ics$/);
  });
});
