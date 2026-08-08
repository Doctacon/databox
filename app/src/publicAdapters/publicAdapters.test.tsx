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
import { PhotoArea } from "../App";
import { getBird, listBirds } from "./birdApi";
import { createObservation, getCollectionState, listLifeList, saveWatch } from "./collectionApi";
import { getMapSnapshot } from "./mapApi";
import { resetPublicRuntimeForTests } from "./runtime";
import { createTargetPlan, getTargetPlan } from "./targetApi";
import { createPlan, getPlan, listPlans, searchLocations } from "./tripApi";
import { TripCalendarControls } from "./TripCalendarControls";
import { evaluateBrowserWatch } from "./watchEvaluation";

function json(value: unknown): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } }));
}

function mockFixtureFetch(weatherResponse?: unknown) {
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
    if (url.startsWith("https://rufous-ai.loughondata.com/v1/weather?") && weatherResponse !== undefined) {
      return json(weatherResponse);
    }
    return url in fixtures ? json(fixtures[url]) : Promise.resolve(new Response("not found", { status: 404 }));
  });
}

function mockLargeCatalogFetch() {
  const compactSpecies = structuredClone(manifest.species).map((species) => ({
    ...species,
    taxonomic_category: "species",
    family: species.species_code === "rufhum"
      ? { common_name: "Hummingbirds", scientific_name: "Trochilidae" }
      : { common_name: null, scientific_name: null },
    order_name: species.species_code === "rufhum" ? "Caprimulgiformes" : null,
    trait_summary: species.species_code === "rufhum"
      ? { status: "available", mass_g: 3.4, habitat: "Woodland edges and flowering gardens" }
      : { status: "unavailable", mass_g: null, habitat: null },
    evidence: species.species_code === "rufhum"
      ? { licensed_occurrence_count: 2, latest_licensed_occurrence_at: "2026-07-31T12:05:00Z" }
      : { licensed_occurrence_count: 0, latest_licensed_occurrence_at: null },
  }));
  const fillerSpecies = Array.from({ length: 48 }, (_, index) => ({
    species_code: `fixture-${index + 1}`,
    common_name: `Fixture Bird ${index + 1}`,
    scientific_name: `Avis fixture${index + 1}`,
    profile_path: `/data/species/fixture-${index + 1}.json`,
    hero_photo: null,
    photo_count: 0,
    taxonomic_category: "species",
    family: { common_name: null, scientific_name: null },
    order_name: null,
    trait_summary: { status: "unavailable", mass_g: null, habitat: null },
    evidence: { licensed_occurrence_count: 0, latest_licensed_occurrence_at: null },
  }));
  const largeManifest = {
    ...structuredClone(manifest),
    source_policy: {
      ...manifest.source_policy,
      trait_source: "synthetic",
      trait_delivery: "inline_static_json",
    },
    species: [...compactSpecies, ...fillerSpecies],
    counts: {
      ...manifest.counts,
      species: compactSpecies.length + fillerSpecies.length,
      species_with_traits: 1,
    },
  };
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    const fixtures: Record<string, unknown> = {
      "/data/manifest.json": largeManifest,
      "/data/cells/n32w111.json": n32w111,
      "/data/cells/n33w113.json": n33w113,
      "/data/cells/n34w113.json": n34w113,
    };
    return url in fixtures ? json(fixtures[url]) : Promise.resolve(new Response("not found", { status: 404 }));
  });
}

const PRODUCTION_SPECIES_CODE = "gbif-2476855";

function publicPhoto(index: number) {
  const prefix = index === 1 ? "ab" : "cd";
  const sha256 = `${prefix}${String(index).repeat(62)}`;
  const inaturalist = index === 1;
  return {
    kind: "photo",
    provider: inaturalist ? "inaturalist" : "usfws",
    media_id: inaturalist ? "inaturalist-5938231789" : `usfws-rufous-${index}`,
    url: `https://rufous-data.loughondata.com/rufous-media/v1/objects/${prefix}/${sha256}.webp`,
    source_url: inaturalist
      ? "https://www.inaturalist.org/photos/5938231789"
      : `https://www.fws.gov/media/rufous-hummingbird-${index}`,
    creator: inaturalist ? "Pat Photographer" : `USFWS Photographer ${index}`,
    license: inaturalist ? "CC BY 4.0" : "Public Domain",
    license_url: inaturalist
      ? "https://creativecommons.org/licenses/by/4.0/"
      : "https://www.fws.gov/notices",
    attribution_id: inaturalist
      ? "inaturalist-attribution-5938231789"
      : `usfws-attribution-${index}`,
    scientific_name: "Selasphorus rufus",
    title: `Rufous Hummingbird ${index}`,
    caption: index === 1 ? "Perched on a twig." : null,
    alt_text: `Rufous Hummingbird photograph ${index}`,
    width: 650,
    height: 488,
    mime_type: "image/webp",
    sha256,
  };
}

function publicAudio() {
  const sha256 = `ef${"4".repeat(62)}`;
  return {
    provider: "xeno_canto",
    provider_id: "XC12345",
    source_url: "https://xeno-canto.org/12345",
    creator: "Pat Recordist",
    license: "CC BY 4.0",
    license_url: "https://creativecommons.org/licenses/by/4.0/",
    url: `https://rufous-data.loughondata.com/rufous-audio/v1/objects/ef/${sha256}.mp3`,
    sha256,
    bytes: 123_456,
    mime_type: "audio/mpeg",
    duration_seconds: 42.5,
    recording_type: "call",
    modifications: "Unmodified from the credited source recording.",
    attribution_id: `audio-attribution-${sha256.slice(0, 24)}`,
  };
}

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
      media_source: "usfws+inaturalist",
      media_delivery: "immutable_r2",
      audio_source: "xeno_canto",
      audio_delivery: "immutable_r2",
    },
    counts: {
      ...manifest.counts,
      species: 1,
      observations: 1,
      media_items: 2,
      species_with_media: 1,
      audio_items: 1,
      species_with_audio: 1,
    },
    species: [{
      species_code: PRODUCTION_SPECIES_CODE,
      common_name: "Rufous Hummingbird",
      scientific_name: "Selasphorus rufus",
      profile_path: `/data/species/${PRODUCTION_SPECIES_CODE}.json`,
      hero_photo: publicPhoto(1),
      photo_count: 2,
      call: publicAudio(),
    }],
    cells: [{ ...n34w113, path: "/data/cells/n34w113.json", observation_count: 1, observations: undefined }],
  };
  const productionProfile = {
    ...structuredClone(rufhum),
    species_code: PRODUCTION_SPECIES_CODE,
    media: [publicPhoto(1), publicPhoto(2)],
    call: publicAudio(),
  };
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
  vi.unstubAllEnvs();
});

describe("full public-app browser adapters", () => {
  it("uses compact catalog metadata without fetching profiles for a large public release", async () => {
    const fetchMock = mockLargeCatalogFetch();

    const catalog = await listBirds();
    const map = await getMapSnapshot();
    const rufous = catalog.find((bird) => bird.species_code === "rufhum");

    expect(catalog).toHaveLength(51);
    expect(rufous).toMatchObject({
      taxonomic_category: "species",
      order_name: "Caprimulgiformes",
      family_common_name: "Hummingbirds",
      family_scientific_name: "Trochilidae",
      traits_status: "available",
      mass_g: 3.4,
      habitat: "Woodland edges and flowering gardens",
      recent_public_observation_count: 2,
      latest_public_observation_at: "2026-07-31T12:05:00.000Z",
    });
    expect(map.encounters.filter((row) => row.species_code === "rufhum")).toEqual(
      expect.arrayContaining([expect.objectContaining({
        family_common_name: "Hummingbirds",
        family_scientific_name: "Trochilidae",
      })]),
    );
    expect(fetchMock.mock.calls.map(([input]) => String(input)).filter((url) => url.includes("/species/"))).toEqual([]);
  });

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
      "load_nws_usgs_weather_elevation",
      "compose_deterministic_field_plan",
    ]);
    expect(trip.weather).toBeNull();
    expect(await listPlans()).toHaveLength(1);
    expect(target.target_plan_id).toMatch(/^target_[0-9a-f]{32}$/);
    expect(target.weather.status).toBe("unavailable");
    expect(target.candidates.length).toBeGreaterThan(0);
    expect(target.caveats.join(" ")).toMatch(/No AI model, email service, or private observation/);
  });

  it("adds one optional NWS and USGS snapshot when configured and reopens it without another request", async () => {
    vi.stubEnv("VITE_RUFOUS_AI_URL", "https://rufous-ai.loughondata.com");
    const weatherResponse = {
      status: "available",
      retrieved_at: "2026-08-08T15:00:00.000Z",
      forecast_summary: {
        temperature_2m_min: 20,
        temperature_2m_max: 24,
        temperature_2m_avg: 22,
        relative_humidity_2m_avg: 40,
        precipitation_probability_max: 10,
        precipitation_sum: null,
        wind_speed_10m_max: 12.5,
        wind_gusts_10m_max: null,
        weather_codes: [],
        condition_summaries: ["Mostly Sunny"],
      },
      elevation_m: 1_636.5,
      caveats: ["NWS forecasts can change.", "USGS elevation is interpolated, not surveyed."],
    };
    const fetchMock = mockFixtureFetch(weatherResponse);
    const [location] = await searchLocations("Prescott");
    const trip = await createPlan({
      location: location.display_name,
      location_selection: location,
      start_at: "2026-08-10T06:30",
      duration_minutes: 120,
      skill_level: "intermediate",
    });

    expect(trip.weather).toMatchObject({
      source: "nws_usgs",
      source_table: "nws_hourly_forecast_usgs_epqs",
      status: "available",
      payload: { elevation_m: 1_636.5, forecast_summary: { condition_summaries: ["Mostly Sunny"] } },
    });
    expect(trip.evidence.filter((item) => item.evidence_type === "weather_elevation_context"))
      .toEqual([trip.weather]);
    expect(trip.tool_traces.map((item) => item.tool_name)).toContain("load_nws_usgs_weather_elevation");
    expect(trip.plan.caveats).toContain("Live NWS forecast and USGS elevation context were retrieved for this plan.");
    const weatherCalls = () => fetchMock.mock.calls.filter(([input]) => String(input).includes("/v1/weather?")).length;
    expect(weatherCalls()).toBe(1);
    expect(await getPlan(trip.plan.trip_plan_id)).toEqual(trip);
    expect(weatherCalls()).toBe(1);
  });

  it("adds the same one-shot NWS and USGS context to a saved target-bird plan", async () => {
    vi.stubEnv("VITE_RUFOUS_AI_URL", "https://rufous-ai.loughondata.com");
    const weatherResponse = {
      status: "partial",
      retrieved_at: "2026-08-08T15:00:00.000Z",
      forecast_summary: null,
      elevation_m: 1_636.5,
      caveats: ["NWS hourly forecast is not yet available.", "USGS elevation is interpolated, not surveyed."],
    };
    const fetchMock = mockFixtureFetch(weatherResponse);
    const [location] = await searchLocations("Prescott");
    const target = await createTargetPlan({
      species_code: "rufhum",
      location: location.display_name,
      location_selection: location,
      radius_miles: 100,
      start_at: "2026-08-10T06:30",
      duration_minutes: 120,
    });

    expect(target.weather).toMatchObject({
      status: "partial",
      elevation_m: 1_636.5,
      units: { temperature: "°C", wind_speed: "km/h", elevation: "m" },
      forecast_summary: { condition_summaries: [] },
    });
    expect(target.guidance.at(-1)).toMatch(/available saved NWS\/USGS context/);
    const weatherCalls = () => fetchMock.mock.calls.filter(([input]) => String(input).includes("/v1/weather?")).length;
    expect(weatherCalls()).toBe(1);
    expect(await getTargetPlan(target.target_plan_id)).toEqual(target);
    expect(weatherCalls()).toBe(1);
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
    const catalog = await listBirds();
    const profile = await getBird(PRODUCTION_SPECIES_CODE);
    const map = await getMapSnapshot();
    const [location] = await searchLocations("Prescott");
    const target = await createTargetPlan({
      species_code: PRODUCTION_SPECIES_CODE,
      location: location.display_name,
      location_selection: location,
      radius_miles: 100,
      start_at: "2026-08-10T06:30",
      duration_minutes: 120,
    });
    const trip = await createPlan({
      location: location.display_name,
      location_selection: location,
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

    expect(profile).toMatchObject({
      species_code: PRODUCTION_SPECIES_CODE,
      common_name: "Rufous Hummingbird",
      photo: { provider: "inaturalist", source_record_id: "inaturalist-5938231789" },
      call: {
        status: "available",
        source_record_id: "XC12345",
        recording_id: "12345",
        recordist: "Pat Recordist",
        audio_url: publicAudio().url,
        source_url: "https://xeno-canto.org/12345",
        license_text: "CC BY 4.0",
      },
    });
    expect(catalog[0].call).toMatchObject(profile.call);
    expect(profile.photos).toHaveLength(2);
    expect(profile.photos?.[1]).toMatchObject({
      provider: "usfws",
      source_url: "https://www.fws.gov/media/rufous-hummingbird-2",
    });
    expect(map.photos).toMatchObject([{
      species_code: PRODUCTION_SPECIES_CODE,
      photo: {
        provider: "inaturalist",
        source_record_id: "inaturalist-5938231789",
        source_url: "https://www.inaturalist.org/photos/5938231789",
      },
    }]);
    expect(trip.recommendations[0].photo).toMatchObject({
      status: "available",
      provider: "inaturalist",
      species_name: "Selasphorus rufus",
      source_record_id: "inaturalist-5938231789",
      source_url: "https://www.inaturalist.org/photos/5938231789",
    });
    expect(trip.recommendations[0].call).toMatchObject({
      status: "available",
      source_record_id: "XC12345",
      recording_id: "12345",
      species_name: "Selasphorus rufus",
      recordist: "Pat Recordist",
      source_url: "https://xeno-canto.org/12345",
      audio_url: publicAudio().url,
      license_text: "CC BY 4.0",
    });
    expect(trip.evidence.filter((item) => item.evidence_type === "recommendation_photo")).toEqual([{
      evidence_id: `photo_1_${PRODUCTION_SPECIES_CODE}`,
      recommendation_id: `recommendation_1_${PRODUCTION_SPECIES_CODE}`,
      source: "inaturalist",
      source_table: "published_inaturalist_media",
      source_record_id: "inaturalist-5938231789",
      evidence_type: "recommendation_photo",
      status: "available",
      retrieved_at: manifest.generated_at,
      summary: {},
      payload: {},
      caveats: [],
    }]);
    expect(trip.evidence.filter((item) => item.evidence_type === "recommendation_call")).toEqual([{
      evidence_id: `call_1_${PRODUCTION_SPECIES_CODE}`,
      recommendation_id: `recommendation_1_${PRODUCTION_SPECIES_CODE}`,
      source: "xeno_canto",
      source_table: "published_xeno_canto_audio",
      source_record_id: "XC12345",
      evidence_type: "recommendation_call",
      status: "available",
      retrieved_at: manifest.generated_at,
      summary: { provider_id: "XC12345", recording_id: "12345" },
      payload: {},
      caveats: [],
    }]);
    expect(trip.media).toEqual([{
      evidence_id: `call_1_${PRODUCTION_SPECIES_CODE}`,
      recommendation_id: `recommendation_1_${PRODUCTION_SPECIES_CODE}`,
      source_record_id: "XC12345",
      recording_id: "12345",
      status: "available",
      species_name: "Selasphorus rufus",
      recording_type: "call",
      quality: null,
      recordist: "Pat Recordist",
      license_text: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
      source_url: "https://xeno-canto.org/12345",
      audio_url: publicAudio().url,
      caveats: [],
    }]);
    render(<PhotoArea row={trip.recommendations[0]} />);
    expect(screen.getByRole("img", { name: "Rufous Hummingbird (Selasphorus rufus)" })).toHaveAttribute(
      "src", publicPhoto(1).url,
    );
    expect(screen.getByRole("link", { name: "View photo source on iNaturalist" })).toHaveAttribute(
      "href", "https://www.inaturalist.org/photos/5938231789",
    );
    expect(screen.getByRole("link", { name: "CC BY 4.0" })).toHaveAttribute(
      "href", "https://creativecommons.org/licenses/by/4.0/",
    );
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
