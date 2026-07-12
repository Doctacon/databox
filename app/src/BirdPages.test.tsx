import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { getBird, listBirds } from "./birdApi";
import type { BirdCatalogSummary, BirdProfile } from "./types";

function response(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json" },
  }));
}

function rawResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body } as Response);
}

const unavailablePhoto = { status: "unavailable" as const, source_record_id: null, species_name: null, display_url: null, source_url: null, creator: null, rights_holder: null, publisher: null, format: null, license_text: null, license_url: null, selection_reason: null, caveats: ["Not enriched"], lookup_at: null };
const unavailableCall = { status: "unavailable" as const, source_record_id: null, recording_id: null, species_name: null, geographic_scope: null, recording_type: null, quality: null, recordist: null, locality: null, country: null, source_url: null, audio_url: null, license_text: null, license_url: null, selection_reason: null, caveats: ["Not enriched"], lookup_at: null };

function bird(index: number): BirdCatalogSummary {
  return {
    species_code: `bird${index.toString().padStart(3, "0")}`,
    common_name: `Arizona Bird ${index.toString().padStart(3, "0")}`,
    scientific_name: `Avis arizona${index.toString().padStart(3, "0")}`,
    taxonomic_category: index < 624 ? "species" : "hybrid",
    taxonomic_order: index,
    order_name: "Passeriformes",
    family_common_name: "Fixture Birds",
    family_scientific_name: "Fixtureidae",
    traits_status: index === 23 || index >= 624 ? "unavailable" : "available",
    mass_g: index === 23 || index >= 624 ? null : 123.4,
    habitat: index === 23 || index >= 624 ? null : "Woodland",
    recent_public_observation_count: index,
    latest_public_observation_at: index ? "2026-07-09T08:00:00" : null,
    photo: unavailablePhoto,
    call: unavailableCall,
  };
}

function withMedia(summary: BirdCatalogSummary, key: number): BirdCatalogSummary {
  const value = structuredClone(summary);
  value.photo = {
    status: "available", source_record_id: String(key), species_name: value.scientific_name,
    display_url: `https://api.gbif.org/v1/image/cache/500x500/occurrence/${key}/media/0123456789abcdef0123456789abcdef`,
    source_url: `https://www.gbif.org/occurrence/${key}`, creator: `Photographer ${key}`,
    rights_holder: null, publisher: "Fixture Archive", format: "image/jpeg",
    license_text: "CC BY 4.0", license_url: "https://creativecommons.org/licenses/by/4.0/",
    selection_reason: "Exact Arizona catalog photo", caveats: [], lookup_at: "2026-07-11T08:00:00Z",
  };
  value.call = {
    status: "available", source_record_id: String(key + 1000), recording_id: String(key + 1000),
    species_name: value.scientific_name, geographic_scope: key % 2 ? "Global example" : "Arizona",
    recording_type: "call", quality: "A", recordist: `Recordist ${key}`, locality: "Fixture Park",
    country: "United States", source_url: `https://xeno-canto.org/${key + 1000}`,
    audio_url: `https://xeno-canto.org/${key + 1000}/download`, license_text: "CC BY-NC-SA 4.0",
    license_url: "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    selection_reason: "Exact species call ranked by type and quality", caveats: [],
    lookup_at: "2026-07-11T08:01:00Z",
  };
  return value;
}

function profile(summary: BirdCatalogSummary = bird(0)): BirdProfile {
  return {
    ...summary,
    region_code: "US-AZ",
    taxonomy: { family_code: "fixture1", report_as: null, extinct: false, extinct_year: null },
    traits: {
      status: summary.traits_status,
      source_scientific_name: summary.traits_status === "available" ? summary.scientific_name : null,
      avonet_family: summary.traits_status === "available" ? "Fixtureidae" : null,
      avonet_order_name: summary.traits_status === "available" ? "Passeriformes" : null,
      avibase_id: summary.traits_status === "available" ? "AVIBASE-FIXTURE" : null,
      inference: summary.traits_status === "available" ? true : null,
      traits_inferred: summary.traits_status === "available" ? "Mass" : null,
      reference_species: summary.traits_status === "available" ? "Reference bird" : null,
      mass_source: summary.traits_status === "available" ? "Measured sample" : null,
      mass_reference_other: null,
      sample: {
        total_individuals: summary.traits_status === "available" ? 4 : null,
        female_individuals: 2, male_individuals: 2, unknown_sex_individuals: 0,
        complete_measures: 4,
      },
      morphology: {
        beak_length_culmen_mm: 30.7, beak_length_nares_mm: 19.7, beak_width_mm: 7.8,
        beak_depth_mm: 10.2, tarsus_length_mm: 44.1, wing_length_mm: 176.5,
        kipps_distance_mm: 52.1, secondary_length_mm: 124.4, hand_wing_index: 29.5,
        tail_length_mm: 150.2, mass_g: 123.4,
      },
      ecology: {
        habitat: "Woodland", habitat_density_code: 2, habitat_density_label: "Semi-open",
        migration_code: 1, migration_label: "Partial migrant", trophic_level: "Omnivore",
        trophic_niche: "Ground", primary_lifestyle: "Insessorial",
      },
      provenance: {
        dataset_doi: summary.traits_status === "available" ? "10.6084/m9.figshare.16586228.v7" : null,
        dataset_version: summary.traits_status === "available" ? "v7" : null,
        dataset_license: summary.traits_status === "available" ? "CC BY 4.0" : null,
        source_file_id: summary.traits_status === "available" ? 34480856 : null,
        source_file_md5: summary.traits_status === "available" ? "1445afdcfb6df784010c2ca034544bc8" : null,
        loaded_at: summary.traits_status === "available" ? "2026-07-10T01:00:00" : null,
      },
    },
    arizona_activity: {
      recent_public_observation_count: summary.recent_public_observation_count,
      latest_public_observation_at: summary.latest_public_observation_at,
      public_location_count: 1,
      recent_public_notable_count: 2,
      top_public_locations: [{
        location_id: "public-1", location_name: "Reviewed Desert Park", latitude: 33.6,
        longitude: -112.1, observation_count: 11,
        latest_observation_at: "2026-07-09T08:00:00", notable_count: 2,
      }],
    },
    gbif: { occurrence_count: 7, latest_event_date: "2026-07-01" },
    xeno_canto: {
      recording_count: 3, latest_recording_date: "2026-06-01",
      representative_recording_id: "123", representative_recordist: "Fixture Birder",
      representative_recording_type: "call", representative_recording_quality: "A",
      representative_recording_license: "CC BY 4.0",
    },
    freshness: {
      species_list_loaded_at: "2026-07-09T01:00:00",
      taxonomy_loaded_at: "2026-07-09T01:00:00",
      ebird_observations_loaded_at: "2026-07-09T01:00:00",
      gbif_loaded_at: "2026-07-09T01:00:00",
      xeno_canto_loaded_at: "2026-07-09T01:00:00",
      catalog_freshness_at: "2026-07-10T01:00:00",
    },
  };
}

beforeEach(() => window.history.replaceState(null, "", "/"));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("Arizona bird catalog and modeled profiles", () => {
  it("renders all 706 stable taxa with bounded paging, search, filters, and reset", async () => {
    const birds = Array.from({ length: 706 }, (_, index) => bird(index));
    window.history.replaceState(null, "", "/birds");
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ birds }));
    render(<App />);

    expect(await screen.findByText("Showing 1–24 of 706 matching taxa · 706 total")).toBeVisible();
    expect(document.querySelectorAll(".bird-catalog-card")).toHaveLength(24);
    expect(screen.getByRole("link", { name: /Arizona Bird 000/ })).toHaveAttribute("href", "/birds/bird000");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "Arizona Bird 024", level: 2 })).toBeVisible();

    await userEvent.selectOptions(screen.getByLabelText("Category"), "hybrid");
    expect(screen.getByText("Showing 1–24 of 82 matching taxa · 706 total")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Arizona Bird 624", level: 2 })).toBeVisible();
    await userEvent.type(screen.getByLabelText("Search birds"), "bird705");
    expect(screen.getByText("Showing 1–1 of 1 matching taxa · 706 total")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Arizona Bird 705", level: 2 })).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Reset catalog" }));
    expect(screen.getByLabelText("Search birds")).toHaveValue("");
    expect(screen.getByLabelText("Category")).toHaveValue("all");
    expect(screen.getByRole("heading", { name: "Arizona Bird 000", level: 2 })).toBeVisible();
  });

  it("renders lazy card media, an original unavailable placeholder, concise attribution, and compact calls", async () => {
    window.history.replaceState(null, "", "/birds");
    const birds = Array.from({ length: 706 }, (_, index) => index === 0 ? withMedia(bird(index), 101) : bird(index));
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ birds }));
    render(<App />);

    const image = await screen.findByRole("img", { name: "Arizona Bird 000 (Avis arizona000)" });
    expect(image).toHaveAttribute("loading", "lazy");
    expect(image).toHaveAttribute("src", birds[0].photo.display_url);
    expect(screen.getByText("Photo: Photographer 101")).toBeVisible();
    expect(screen.getByRole("link", { name: "GBIF source" })).toHaveAttribute("href", birds[0].photo.source_url);
    expect(screen.getByRole("button", { name: "Play call for Arizona Bird 000" })).toHaveAttribute("aria-pressed", "false");
    expect(document.querySelector("audio")).toHaveAttribute("preload", "none");
    expect(screen.getByText("Call: Recordist 101 · Global example")).toBeVisible();
    const placeholder = screen.getByRole("img", { name: "No licensed photo available for Arizona Bird 001 (Avis arizona001)" });
    expect(placeholder).toBeVisible();
    expect(placeholder.querySelector("img")).toHaveAttribute("src", expect.stringContaining("rufous.png"));
    expect(screen.getAllByText("No validated call is available.").length).toBeGreaterThan(0);
  });

  it("keeps one catalog call active and stops playback when filtering", async () => {
    window.history.replaceState(null, "", "/birds");
    const birds = Array.from({ length: 706 }, (_, index) => index < 25 ? withMedia(bird(index), index + 1) : bird(index));
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    const pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path === "/api/birds") return response({ birds });
      if (path === "/api/birds/bird000") return response(profile(birds[0]));
      if (path === "/api/birds/bird000/collection-state") return response({ species_code: "bird000", catalog_status: "current", observed: false, observation_count: 0, watched: false, watch_active: false });
      throw new Error(`Unexpected request ${path}`);
    });
    const rendered = render(<App />);

    const first = await screen.findByRole("button", { name: "Play call for Arizona Bird 000" });
    const second = screen.getByRole("button", { name: "Play call for Arizona Bird 001" });
    await userEvent.click(first);
    expect(play).toHaveBeenCalledTimes(1);
    expect(first).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(second);
    expect(play).toHaveBeenCalledTimes(2);
    expect(first).toHaveAttribute("aria-pressed", "false");
    expect(second).toHaveAttribute("aria-pressed", "true");

    await userEvent.type(screen.getByLabelText("Search birds"), "bird001");
    await waitFor(() => expect(second).toHaveAttribute("aria-pressed", "false"));
    expect(pause).toHaveBeenCalled();
    rendered.unmount();
  });

  it("stops catalog calls on pagination, route changes, and unmount", async () => {
    window.history.replaceState(null, "", "/birds");
    const birds = Array.from({ length: 706 }, (_, index) => index < 25 ? withMedia(bird(index), index + 1) : bird(index));
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path === "/api/birds") return response({ birds });
      if (path === "/api/birds/bird000") return response(profile(birds[0]));
      if (path === "/api/birds/bird000/collection-state") return response({ species_code: "bird000", catalog_status: "current", observed: false, observation_count: 0, watched: false, watch_active: false });
      throw new Error(`Unexpected request ${path}`);
    });
    const rendered = render(<App />);

    const firstPageCall = await screen.findByRole("button", { name: "Play call for Arizona Bird 000" });
    await userEvent.click(firstPageCall);
    expect(firstPageCall).toHaveAttribute("aria-pressed", "true");
    const pageAudio = document.querySelector("audio");
    expect(pageAudio).not.toBeNull();
    const pagePause = vi.spyOn(pageAudio!, "pause");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(pagePause).toHaveBeenCalled());

    await userEvent.click(screen.getByRole("button", { name: "Previous" }));
    await userEvent.click(await screen.findByRole("button", { name: "Play call for Arizona Bird 000" }));
    const routeAudio = document.querySelector("audio");
    expect(routeAudio).not.toBeNull();
    const routePause = vi.spyOn(routeAudio!, "pause");
    await userEvent.click(screen.getByRole("link", { name: "Arizona Bird 000" }));
    expect(await screen.findByRole("heading", { name: "Arizona Bird 000", level: 1 })).toBeVisible();
    expect(routePause).toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Play call for Arizona Bird 000" }));
    const profileAudio = document.querySelector("audio");
    expect(profileAudio).not.toBeNull();
    const unmountPause = vi.spyOn(profileAudio!, "pause");
    rendered.unmount();
    expect(unmountPause).toHaveBeenCalled();
  });

  it("preserves attribution and shows safe image and call load errors", async () => {
    window.history.replaceState(null, "", "/birds");
    const birds = Array.from({ length: 706 }, (_, index) => index === 0 ? withMedia(bird(index), 101) : bird(index));
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ birds }));
    render(<App />);

    const image = await screen.findByRole("img", { name: "Arizona Bird 000 (Avis arizona000)" });
    fireEvent.error(image);
    expect(screen.getByText("Photo could not be loaded.")).toBeVisible();
    expect(screen.getByText("Photo: Photographer 101")).toBeVisible();
    const audio = document.querySelector("audio");
    expect(audio).not.toBeNull();
    fireEvent.error(audio!);
    expect(screen.getByText("Call playback failed.")).toBeVisible();
    expect(screen.getByText("Call: Recordist 101 · Global example")).toBeVisible();
  });

  it("shows full profile media attribution, scope, selection reason, and lookup freshness", async () => {
    window.history.replaceState(null, "", "/birds/bird000");
    const summary = withMedia(bird(0), 102);
    const modeled = profile(summary);
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path.endsWith("/collection-state")) return response({ species_code: "bird000", catalog_status: "current", observed: false, observation_count: 0, watched: false, watch_active: false });
      return response(modeled);
    });
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Photo and call" })).toBeVisible();
    expect(document.querySelector(".catalog-photo-profile img")).toHaveAttribute("loading", "lazy");
    expect(screen.getByText("Publisher: Fixture Archive")).toBeVisible();
    expect(screen.getByText("Exact Arizona catalog photo")).toBeVisible();
    expect(screen.getByText("Call: Recordist 102 · Arizona")).toBeVisible();
    expect(screen.getByText("Type: call · quality A")).toBeVisible();
    expect(screen.getByText("Location: Fixture Park, United States")).toBeVisible();
    expect(screen.getByText("Exact species call ranked by type and quality")).toBeVisible();
    expect(screen.getAllByText(/Looked up:/)).toHaveLength(2);
    expect(document.querySelector(".catalog-call-profile audio")).toHaveAttribute("preload", "none");
  });

  it("supports native navigation, direct detail routes, and popstate without a router dependency", async () => {
    const rows = Array.from({ length: 706 }, (_, index) => bird(index));
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path === "/api/trip-plans") return response({ plans: [] });
      if (path === "/api/birds") return response({ birds: rows });
      if (path === "/api/birds/bird000") return response(profile(rows[0]));
      if (path === "/api/birds/bird000/collection-state") return response({ species_code: "bird000", catalog_status: "current", observed: false, observation_count: 0, watched: false, watch_active: false });
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "No trip selected" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Plan your next local birding outing", level: 1 })).toHaveFocus();
    expect(document.title).toBe("Trip Planner · Rufous");

    await userEvent.click(screen.getByRole("link", { name: "Arizona Birds" }));
    const catalogHeading = await screen.findByRole("heading", { name: "Arizona Birds", level: 1 });
    expect(catalogHeading).toHaveFocus();
    expect(document.title).toBe("Arizona Birds · Rufous");
    expect(window.location.pathname).toBe("/birds");
    await userEvent.click(screen.getByRole("link", { name: /Arizona Bird 000/ }));
    const profileHeading = await screen.findByRole("heading", { name: "Arizona Bird 000", level: 1 });
    expect(profileHeading).toHaveFocus();
    expect(document.title).toBe("Arizona Bird 000 · Arizona Birds · Rufous");
    expect(window.location.pathname).toBe("/birds/bird000");

    window.history.pushState(null, "", "/birds");
    window.dispatchEvent(new PopStateEvent("popstate"));
    const restoredCatalogHeading = await screen.findByRole("heading", { name: "Arizona Birds", level: 1 });
    expect(restoredCatalogHeading).toHaveFocus();
    expect(document.title).toBe("Arizona Birds · Rufous");
    await userEvent.click(screen.getByRole("link", { name: "Trip Planner" }));
    expect(await screen.findByRole("heading", { name: "No trip selected" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Plan your next local birding outing", level: 1 })).toHaveFocus();
    expect(document.title).toBe("Trip Planner · Rufous");
  });

  it("renders exact modeled sections, units, labels, inference, sources, and public locations", async () => {
    window.history.replaceState(null, "", "/birds/bird000");
    const modeledProfile = profile();
    modeledProfile.arizona_activity.top_public_locations[0].location_name = "Odell Lake (private)";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path === "/api/birds/bird000/collection-state") return response({
        species_code: "bird000", catalog_status: "current", observed: false,
        observation_count: 0, watched: false, watch_active: false,
      });
      if (path === "/api/watches") return response({ watches: [] });
      return response(modeledProfile);
    });
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Arizona Bird 000", level: 1 })).toBeVisible();
    for (const section of [
      "Identity and taxonomy", "Physical traits", "Ecology", "Arizona activity",
      "Occurrence and sound context", "Evidence and provenance",
    ]) expect(screen.getByRole("heading", { name: section })).toBeVisible();
    expect(screen.getByText("176.5 mm")).toBeVisible();
    expect(screen.getByText("123.4 g")).toBeVisible();
    expect(screen.getByText("Semi-open (code 2)")).toBeVisible();
    expect(screen.getByText("Partial migrant (code 1)")).toBeVisible();
    expect(screen.getByText(/Global range metrics are not available in the governed model/)).toBeVisible();
    expect(screen.getByText("1445afdcfb6df784010c2ca034544bc8")).toBeVisible();
    expect(screen.getByText(/AVONET marks modeled traits as inferred: Mass/)).toHaveTextContent("Reference species: Reference bird");
    const location = screen.getByText("Odell Lake (private)").closest("li");
    expect(location).not.toBeNull();
    expect(within(location!).getByText("33.6000, -112.1000")).toBeVisible();
    expect(within(location!).getByText(/site access may be restricted/i)).toHaveTextContent(
      "Verify access before visiting.",
    );
    expect(screen.getByRole("link", { name: /AVONET dataset DOI/ })).toHaveAttribute(
      "href", "https://doi.org/10.6084/m9.figshare.16586228.v7",
    );
    expect(screen.getByRole("link", { name: "CC BY 4.0" })).toHaveAttribute(
      "href", "https://creativecommons.org/licenses/by/4.0/",
    );
    expect(screen.getByText("Catalog and public observation snapshot loaded")).toBeVisible();
    expect(screen.getByText("Exact trait match available")).toBeVisible();
    expect(screen.getByText("Modeled occurrence evidence available")).toBeVisible();
    expect(screen.getByText("Modeled recording evidence available")).toBeVisible();
    expect(screen.getByText(/do not run matching, weather, a model, calendar, or email/i)).toBeVisible();
    expect(document.querySelector("audio, iframe")).toBeNull();
    expect(screen.getByRole("img", { name: "No licensed photo available for Arizona Bird 000 (Avis arizona000)" })).toBeVisible();
    expect(screen.queryByText(/map/i)).not.toBeInTheDocument();
  });

  it.each([
    [404, "Bird not found in the Arizona catalog"],
    [503, "The warehouse is refreshing; try again shortly"],
  ])("renders safe modeled profile API errors (%i)", async (status, message) => {
    window.history.replaceState(null, "", "/birds/bird000");
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ error: {
      code: status === 404 ? "not_found" : "database_busy", message,
    } }, status));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("heading", { name: "Bird profile unavailable", level: 1 })).toHaveFocus();
    expect(document.title).toBe("Bird Profile Unavailable · Arizona Birds · Rufous");
    expect(document.body).not.toHaveTextContent("/private/");
  });

  it("rejects undersized and duplicate catalog snapshots", async () => {
    window.history.replaceState(null, "", "/birds");
    const undersized = Array.from({ length: 705 }, (_, index) => bird(index));
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ birds: undersized }));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load Arizona birds");
    cleanup();

    vi.restoreAllMocks();
    const duplicate = Array.from({ length: 706 }, (_, index) => bird(index));
    duplicate[705] = bird(0);
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ birds: duplicate }));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load Arizona birds");
  });

  it.each([
    ["arbitrary", "form"],
    ["null", null],
  ])("rejects %s taxonomic categories", async (_name, category) => {
    window.history.replaceState(null, "", "/birds");
    const invalid = Array.from({ length: 706 }, (_, index) => bird(index));
    (invalid[0] as unknown as { taxonomic_category: unknown }).taxonomic_category = category;
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ birds: invalid }));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load Arizona birds");
  });

  it("rejects a unique 625 species and 81 hybrid distribution", async () => {
    window.history.replaceState(null, "", "/birds");
    const invalid = Array.from({ length: 706 }, (_, index) => bird(index));
    invalid[624] = { ...invalid[624], taxonomic_category: "species" };
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ birds: invalid }));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load Arizona birds");
  });

  it("rejects impossible and non-ISO bird dates across nested response families", async () => {
    const mutations: ((value: BirdProfile) => void)[] = [
      (value) => { value.latest_public_observation_at = "2026-02-29T08:00:00"; value.arizona_activity.latest_public_observation_at = value.latest_public_observation_at; },
      (value) => { value.traits.provenance.loaded_at = "2026-04-31T08:00:00"; },
      (value) => { value.arizona_activity.top_public_locations[0].latest_observation_at = "2026-01-01T24:00:00"; },
      (value) => { value.gbif.latest_event_date = "0"; },
      (value) => { value.xeno_canto.latest_recording_date = "2026-02-29"; },
      (value) => { value.freshness.catalog_freshness_at = "2026-01-01T08:00:00+24:00"; },
    ];
    for (const mutate of mutations) {
      const invalid = profile(); mutate(invalid);
      vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response(invalid));
      await expect(getBird("bird000")).rejects.toThrow();
    }
    const invalidCatalog = Array.from({ length: 706 }, (_, index) => bird(index));
    invalidCatalog[1].latest_public_observation_at = "2026-04-31T08:00:00";
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({ birds: invalidCatalog }));
    await expect(listBirds()).rejects.toThrow();
  });

  it("accepts exact backend date, leap-day, UTC, offset, fractional, and naive timestamp forms", async () => {
    const valid = profile();
    valid.latest_public_observation_at = "2024-02-29T08:00:00.123456Z";
    valid.arizona_activity.latest_public_observation_at = valid.latest_public_observation_at;
    valid.arizona_activity.top_public_locations[0].latest_observation_at = "2024-02-29T01:00:00-07:00";
    valid.traits.provenance.loaded_at = "2024-02-29T08:00:00";
    valid.gbif.latest_event_date = "2024-02-29";
    valid.xeno_canto.latest_recording_date = "2024-02-29";
    for (const key of Object.keys(valid.freshness) as (keyof BirdProfile["freshness"])[]) {
      valid.freshness[key] = key === "catalog_freshness_at" ? "2024-02-29T08:00:00+00:00" : "2024-02-29T08:00:00";
    }
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(valid));
    await expect(getBird("bird000")).resolves.toEqual(valid);
  });

  it("strictly validates catalog media identity, URLs, licenses, fields, and dates", async () => {
    const available = bird(0);
    available.photo = {
      status: "available", source_record_id: "101", species_name: available.scientific_name,
      display_url: "https://api.gbif.org/v1/image/cache/500x500/occurrence/101/media/0123456789abcdef0123456789abcdef",
      source_url: "https://www.gbif.org/occurrence/101", creator: "Fixture", rights_holder: null,
      publisher: "Archive", format: "image/jpeg", license_text: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/", selection_reason: "Exact",
      caveats: [], lookup_at: "2026-07-11T08:00:00Z",
    };
    available.call = {
      status: "available", source_record_id: "201", recording_id: "201",
      species_name: available.scientific_name, geographic_scope: "Arizona", recording_type: "call",
      quality: "A", recordist: "Fixture", locality: "Arizona", country: "United States",
      source_url: "https://xeno-canto.org/201", audio_url: "https://xeno-canto.org/201/download",
      license_text: "CC BY-NC-SA 4.0", license_url: "https://creativecommons.org/licenses/by-nc-sa/4.0/",
      selection_reason: "Exact", caveats: [], lookup_at: "2026-07-11T08:00:00Z",
    };
    const catalog = Array.from({ length: 706 }, (_, index) => index ? bird(index) : available);
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({ birds: catalog }));
    await expect(listBirds()).resolves.toHaveLength(706);
    for (const mutate of [
      (value: BirdCatalogSummary) => { value.photo.species_name = "Wrong species"; },
      (value: BirdCatalogSummary) => { value.photo.display_url = "https://evil.example/photo"; },
      (value: BirdCatalogSummary) => { value.photo.license_text = "All rights reserved"; },
      (value: BirdCatalogSummary) => { value.call.audio_url = "https://evil.example/audio"; },
      (value: BirdCatalogSummary) => { (value.photo as unknown as { publisher: unknown }).publisher = 42; },
      (value: BirdCatalogSummary) => { value.call.recordist = "x".repeat(1001); },
      (value: BirdCatalogSummary) => { value.call.lookup_at = "2026-02-29T08:00:00"; },
      (value: BirdCatalogSummary) => { (value.photo as unknown as Record<string, unknown>).extra = true; },
    ]) {
      const invalid = structuredClone(catalog); mutate(invalid[0]);
      vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({ birds: invalid }));
      await expect(listBirds()).rejects.toThrow();
    }
  });

  it("strictly validates catalog summary mass, habitat, and exact keys", async () => {
    const mutations: ((value: BirdCatalogSummary) => void)[] = [
      (value) => { value.mass_g = 0; },
      (value) => { value.mass_g = -1; },
      (value) => { value.mass_g = Number.NaN; },
      (value) => { value.mass_g = Number.POSITIVE_INFINITY; },
      (value) => { (value as unknown as { mass_g: unknown }).mass_g = "123.4"; },
      (value) => { value.habitat = ""; },
      (value) => { value.habitat = "   \t"; },
      (value) => { value.habitat = "x".repeat(201); },
      (value) => { value.habitat = "Woodland\nprivate detail"; },
      (value) => { (value as unknown as { habitat: unknown }).habitat = 42; },
      (value) => { (value as unknown as Record<string, unknown>).extra = true; },
      (value) => { value.traits_status = "unavailable"; },
    ];
    for (const mutate of mutations) {
      const catalog = Array.from({ length: 706 }, (_, index) => bird(index));
      mutate(catalog[0]);
      vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => rawResponse({ birds: catalog }));
      await expect(listBirds()).rejects.toThrow();
    }
    const hybridLeak = Array.from({ length: 706 }, (_, index) => bird(index));
    hybridLeak[0].taxonomic_category = "hybrid";
    hybridLeak[624].taxonomic_category = "species";
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => rawResponse({ birds: hybridLeak }));
    await expect(listBirds()).rejects.toThrow();

    const exact = Array.from({ length: 706 }, (_, index) => bird(index));
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => rawResponse({ birds: exact }));
    const validated = await listBirds();
    expect(validated[0]).toMatchObject({ mass_g: 123.4, habitat: "Woodland" });
    expect(validated.slice(624).every((value) => value.mass_g === null && value.habitat === null)).toBe(true);
  });

  it("suppresses malformed or unexpected API error payloads", async () => {
    window.history.replaceState(null, "", "/birds/bird000");
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ error: {
      code: "database_busy", message: "/private/warehouse.duckdb", detail: "secret",
    } }, 503));
    render(<App />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The local bird catalog is unavailable");
    expect(alert).not.toHaveTextContent("/private/warehouse.duckdb");
    expect(alert).not.toHaveTextContent("secret");
  });

  it.each([
    [true, /AVONET marks modeled traits as inferred/],
    [false, /AVONET does not mark these modeled traits as inferred/],
    [null, /AVONET inference status is unavailable/],
  ])("renders inference status %s distinctly", async (inference, expected) => {
    window.history.replaceState(null, "", "/birds/bird000");
    const modeledProfile = profile();
    modeledProfile.traits.inference = inference;
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(modeledProfile));
    render(<App />);
    expect(await screen.findByText(expected)).toBeVisible();
  });

  it("keeps hybrid, taxonomy-drift, sparse, and invalid payload states safe", async () => {
    const hybrid = bird(624);
    const sparse = profile(hybrid);
    sparse.traits.sample = {
      total_individuals: null, female_individuals: null, male_individuals: null,
      unknown_sex_individuals: null, complete_measures: null,
    };
    sparse.traits.morphology = Object.fromEntries(
      Object.keys(sparse.traits.morphology).map((key) => [key, null]),
    ) as unknown as BirdProfile["traits"]["morphology"];
    sparse.traits.ecology = {
      habitat: null, habitat_density_code: null, habitat_density_label: null,
      migration_code: null, migration_label: null, trophic_level: null,
      trophic_niche: null, primary_lifestyle: null,
    };
    sparse.arizona_activity = {
      recent_public_observation_count: hybrid.recent_public_observation_count,
      latest_public_observation_at: hybrid.latest_public_observation_at,
      public_location_count: 0, recent_public_notable_count: 0, top_public_locations: [],
    };
    sparse.gbif = { occurrence_count: 0, latest_event_date: null };
    sparse.xeno_canto = {
      recording_count: 0, latest_recording_date: null, representative_recording_id: null,
      representative_recordist: null, representative_recording_type: null,
      representative_recording_quality: null, representative_recording_license: null,
    };
    window.history.replaceState(null, "", "/birds/bird624");
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response(sparse));
    render(<App />);
    expect(await screen.findByText("Hybrid · bird624")).toBeVisible();
    expect(screen.getByText(/AVONET v7 has no exact scientific-name match/)).toBeVisible();
    expect(screen.getByText("No recent valid, reviewed, non-private Arizona locations are available.")).toBeVisible();
    expect(screen.getByText("No modeled GBIF occurrences are available.")).toBeVisible();
    expect(screen.getByText("No modeled Xeno-canto recordings are available.")).toBeVisible();
    expect(screen.getByText("No exact trait match")).toBeVisible();
    expect(screen.getByText("No modeled occurrence evidence")).toBeVisible();
    expect(screen.getByText("No modeled recording evidence")).toBeVisible();
    cleanup();

    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ species_code: "bird000", private_location: "secret" }));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load this bird");
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });
});
