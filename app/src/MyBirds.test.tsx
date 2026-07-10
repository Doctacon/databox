import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { BirdCatalogSummary, BirdProfile, BirdWatch, PersonalObservation } from "./types";

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}
function catalog(): BirdCatalogSummary[] {
  return Array.from({ length: 706 }, (_, index) => ({
    species_code: `bird${index.toString().padStart(3, "0")}`,
    common_name: `Arizona Bird ${index.toString().padStart(3, "0")}`,
    scientific_name: `Avis localis${index}`,
    taxonomic_category: index < 624 ? "species" : "hybrid",
    taxonomic_order: index,
    order_name: "Passeriformes",
    family_common_name: "Local Birds",
    family_scientific_name: "Localidae",
    traits_status: index < 600 ? "available" : "unavailable",
    recent_public_observation_count: 0,
    latest_public_observation_at: null,
  }));
}
const identity = { catalog_status: "current" as const, common_name: "Arizona Bird 000", scientific_name: "Avis localis0", taxonomic_category: "species" as const };
const staleIdentity = { catalog_status: "stale" as const, common_name: null, scientific_name: null, taxonomic_category: null };
function observation(overrides: Partial<PersonalObservation> = {}): PersonalObservation {
  return { observation_id: "obs-1", species_code: "bird000", observation_date: "2026-07-09", location: null, notes: null, created_at: "2026-07-10T01:00:00Z", updated_at: "2026-07-10T01:00:00Z", identity, ...overrides };
}
function watched(overrides: Partial<BirdWatch> = {}): BirdWatch {
  return { species_code: "bird000", active: true, center_name: "Prescott, Arizona", center_latitude: 34.54, center_longitude: -112.47, center_timezone: "America/Phoenix", radius_miles: 25, activated_at: "2026-07-10T01:00:00Z", created_at: "2026-07-10T01:00:00Z", updated_at: "2026-07-10T01:00:00Z", identity, ...overrides };
}
function profile(): BirdProfile {
  const summary = catalog()[0];
  return { ...summary, region_code: "US-AZ", taxonomy: { family_code: null, report_as: null, extinct: false, extinct_year: null }, traits: { status: "available", source_scientific_name: summary.scientific_name, avonet_family: null, avonet_order_name: null, avibase_id: null, inference: false, traits_inferred: null, reference_species: null, mass_source: null, mass_reference_other: null, sample: { total_individuals: 1, female_individuals: null, male_individuals: null, unknown_sex_individuals: 1, complete_measures: 1 }, morphology: { beak_length_culmen_mm: null, beak_length_nares_mm: null, beak_width_mm: null, beak_depth_mm: null, tarsus_length_mm: null, wing_length_mm: null, kipps_distance_mm: null, secondary_length_mm: null, hand_wing_index: null, tail_length_mm: null, mass_g: null }, ecology: { habitat: null, habitat_density_code: null, habitat_density_label: null, migration_code: null, migration_label: null, trophic_level: null, trophic_niche: null, primary_lifestyle: null }, provenance: { dataset_doi: null, dataset_version: null, dataset_license: null, source_file_id: null, source_file_md5: null, loaded_at: null } }, arizona_activity: { recent_public_observation_count: 0, latest_public_observation_at: null, public_location_count: 0, recent_public_notable_count: 0, top_public_locations: [] }, gbif: { occurrence_count: 0, latest_event_date: null }, xeno_canto: { recording_count: 0, latest_recording_date: null, representative_recording_id: null, representative_recordist: null, representative_recording_type: null, representative_recording_quality: null, representative_recording_license: null }, freshness: { species_list_loaded_at: null, taxonomy_loaded_at: null, ebird_observations_loaded_at: null, gbif_loaded_at: null, xeno_canto_loaded_at: null, catalog_freshness_at: null } };
}

beforeEach(() => window.history.replaceState(null, "", "/my-birds"));
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState(null, "", "/"); });

function emptyCollectionMock() {
  const birds = catalog();
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const path = String(input);
    if (path === "/api/birds") return json({ birds });
    if (path === "/api/observations") return json({ observations: [] });
    if (path === "/api/life-list") return json({ birds: [] });
    if (path === "/api/wishlist") return json({ birds: [] });
    if (path === "/api/watches") return json({ watches: [] });
    throw new Error(`Unexpected request ${path}`);
  });
}

describe("My Birds and profile collection controls", () => {
  it("supports direct navigation, native tabs, title, heading focus, empty and back-forward states", async () => {
    emptyCollectionMock();
    render(<App />);
    const heading = await screen.findByRole("heading", { name: "My Birds", level: 1 });
    expect(heading).toHaveFocus();
    expect(document.title).toBe("My Birds · Databox");
    expect(screen.getByRole("link", { name: "My Birds" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText(/life list is empty/i)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Observations" }));
    expect(screen.getByRole("heading", { name: "Observations" })).toBeVisible();
    expect(screen.getByText("No observations recorded yet.")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Wishlist" }));
    expect(screen.getByText("Your wishlist is empty.")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Watches" }));
    expect(screen.getByText("You are not watching any birds.")).toBeVisible();
    window.history.pushState(null, "", "/birds"); window.dispatchEvent(new PopStateEvent("popstate"));
    expect(await screen.findByRole("heading", { name: "Arizona Birds", level: 1 })).toHaveFocus();
  });

  it("records, edits, and explicitly hard-deletes observations while refreshing life-list state", async () => {
    const birds = catalog(); let rows: PersonalObservation[] = []; const calls: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input); calls.push(`${init?.method || "GET"} ${path}`);
      if (path === "/api/birds") return json({ birds });
      if (path === "/api/observations" && init?.method === "POST") { const body = JSON.parse(String(init.body)); rows = [observation({ observation_date: body.observation_date, location: body.location, notes: body.notes })]; return json(rows[0], 201); }
      if (path === "/api/observations/obs-1" && init?.method === "PUT") { const body = JSON.parse(String(init.body)); rows = [observation({ observation_date: body.observation_date, location: body.location, notes: body.notes, updated_at: "2026-07-10T02:00:00Z" })]; return json(rows[0]); }
      if (path === "/api/observations/obs-1?confirm=true" && init?.method === "DELETE") { rows = []; return json({ removed: true }); }
      if (path === "/api/observations") return json({ observations: rows });
      if (path === "/api/life-list") return json({ birds: rows.length ? [{ species_code: "bird000", first_observed_date: rows[0].observation_date, latest_observed_date: rows[0].observation_date, observation_count: 1, identity }] : [] });
      if (path === "/api/wishlist") return json({ birds: [] });
      if (path === "/api/watches") return json({ watches: [] });
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Observations" }));
    await userEvent.type(screen.getByLabelText("Observation date"), "2026-07-09");
    await userEvent.type(screen.getByLabelText(/Location \(optional personal note\)/), "Local trail");
    await userEvent.type(screen.getByLabelText(/Notes \(optional\)/), "Seen near water");
    await userEvent.click(screen.getByRole("button", { name: "Record observation" }));
    expect(await screen.findByText("Observation recorded.")).toBeVisible();
    expect(screen.getByText("Local trail", { exact: false })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const editRegion = screen.getByRole("heading", { name: /Edit Arizona Bird/ }).parentElement!;
    const notes = within(editRegion).getByLabelText(/Notes/);
    await userEvent.clear(notes); await userEvent.type(notes, "Updated note");
    await userEvent.click(within(editRegion).getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Observation updated.")).toBeVisible();
    expect(screen.getByText("Updated note")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Delete permanently" }));
    let dialog = screen.getByRole("dialog", { name: /Permanently delete/ });
    expect(dialog).toHaveTextContent("cannot be undone");
    const cancelDelete = within(dialog).getByRole("button", { name: "Cancel" });
    const confirmDelete = within(dialog).getByRole("button", { name: "Delete permanently" });
    expect(cancelDelete).toHaveFocus();
    await userEvent.tab({ shift: true }); expect(confirmDelete).toHaveFocus();
    await userEvent.tab(); expect(cancelDelete).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: /Permanently delete/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete permanently" }));
    dialog = screen.getByRole("dialog", { name: /Permanently delete/ });
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete permanently" }));
    expect(await screen.findByText("Observation permanently deleted.")).toBeVisible();
    expect(screen.getByText("No observations recorded yet.")).toBeVisible();
    expect(calls).toContain("DELETE /api/observations/obs-1?confirm=true");
  });

  it("keeps wishlist and watch controls independent, supports edit/pause/resume, and marks stale state", async () => {
    const birds = catalog(); let wishlisted = false; let currentWatch: BirdWatch | null = { ...watched(), identity: staleIdentity };
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/birds") return json({ birds });
      if (path === "/api/observations") return json({ observations: [] });
      if (path === "/api/life-list") return json({ birds: [] });
      if (path === "/api/wishlist/bird000" && init?.method === "PUT") { wishlisted = true; return json({ species_code: "bird000", created_at: "2026-07-10T01:00:00Z", identity }); }
      if (path === "/api/wishlist/bird000" && init?.method === "DELETE") { wishlisted = false; return json({ removed: true }); }
      if (path === "/api/wishlist") return json({ birds: wishlisted ? [{ species_code: "bird000", created_at: "2026-07-10T01:00:00Z", identity }] : [] });
      if (path === "/api/watches/bird000/pause" && init?.method === "POST") { currentWatch = { ...currentWatch!, active: false }; return json(currentWatch); }
      if (path === "/api/watches/bird000/resume" && init?.method === "POST") return json({ error: { code: "species_not_found", message: "ignored" } }, 404);
      if (path === "/api/watches/bird000" && init?.method === "PUT") { const body = JSON.parse(String(init.body)); currentWatch = { ...currentWatch!, center_name: body.center.display_name, radius_miles: body.radius_miles }; return json(currentWatch); }
      if (path === "/api/watches") return json({ watches: currentWatch ? [currentWatch] : [] });
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Wishlist" }));
    await userEvent.selectOptions(screen.getByLabelText("Add a bird"), "bird000");
    await userEvent.click(screen.getByRole("button", { name: "Add to wishlist" }));
    expect(await screen.findByText("Bird added to wishlist.")).toBeVisible();
    expect(screen.getByText("Arizona Bird 000", { selector: "strong" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Watches" }));
    expect(screen.getByText("No longer in the current Arizona catalog")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(await screen.findByText("Watch paused.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Resume" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Edit center or radius" }));
    const edit = screen.getByRole("heading", { name: /Edit watch/ }).parentElement!;
    const radius = within(edit).getByLabelText("Travel radius (miles)"); await userEvent.clear(radius); await userEvent.type(radius, "40");
    await userEvent.click(within(edit).getByRole("button", { name: "Save watch" }));
    expect(await screen.findByText("Watch updated.")).toBeVisible();
    expect(screen.getByText(/40 miles/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Wishlist" }));
    expect(screen.getByText("Arizona Bird 000", { selector: "strong" })).toBeVisible();
  });

  it("creates and confirmed-deletes a per-watch Arizona center and radius without a global origin", async () => {
    const birds = catalog(); let currentWatch: BirdWatch | null = null; const calls: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input); calls.push(`${init?.method || "GET"} ${path}`);
      if (path === "/api/birds") return json({ birds });
      if (path === "/api/observations") return json({ observations: [] });
      if (path === "/api/life-list") return json({ birds: [] });
      if (path === "/api/wishlist") return json({ birds: [] });
      if (path === "/api/watches") return json({ watches: currentWatch ? [currentWatch] : [] });
      if (path === "/api/locations?q=Prescott") return json({ locations: [{ display_name: "Prescott, Arizona", latitude: 34.54, longitude: -112.47, timezone: "America/Phoenix", region_code: "US-AZ" }] });
      if (path === "/api/watches/bird000" && init?.method === "PUT") { const body = JSON.parse(String(init.body)); currentWatch = { ...watched(), center_name: body.center.display_name, radius_miles: body.radius_miles }; return json(currentWatch); }
      if (path === "/api/watches/bird000" && init?.method === "DELETE") { currentWatch = null; return json({ removed: true }); }
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Watches" }));
    await userEvent.selectOptions(screen.getByLabelText("Bird"), "bird000");
    await userEvent.type(screen.getByLabelText("Watch center"), "Prescott");
    await userEvent.click(await screen.findByRole("option", { name: /Prescott, Arizona/ }));
    const radius = screen.getByLabelText("Travel radius (miles)"); await userEvent.clear(radius); await userEvent.type(radius, "35");
    await userEvent.click(screen.getByRole("button", { name: "Start watching" }));
    expect(await screen.findByText("Watch created.")).toBeVisible();
    const watchRow = screen.getByText(/Prescott, Arizona · 35 miles/).closest("li");
    expect(watchRow).not.toBeNull();
    expect(within(watchRow!).getByText(/does not save a global home location/i)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Delete watch" }));
    const dialog = screen.getByRole("dialog", { name: "Delete this watch?" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete watch" }));
    expect(await screen.findByText("Watch deleted.")).toBeVisible();
    expect(screen.getByText("You are not watching any birds.")).toBeVisible();
    expect(calls.some((call) => call.includes("smtp") || call.includes("calendar") || call.includes("weather"))).toBe(false);
  });

  it("exposes explicit profile controls without implicit mutations or downstream calls", async () => {
    window.history.replaceState(null, "", "/birds/bird000"); const birds = catalog(); let wishlisted = false; const calls: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input); calls.push(`${init?.method || "GET"} ${path}`);
      if (path === "/api/birds/bird000") return json(profile());
      if (path === "/api/birds/bird000/collection-state") return json({ species_code: "bird000", catalog_status: "current", observed: false, observation_count: 0, wishlisted, watched: false, watch_active: false });
      if (path === "/api/watches") return json({ watches: [] });
      if (path === "/api/wishlist/bird000" && init?.method === "PUT") { wishlisted = true; return json({ species_code: "bird000", created_at: "2026-07-10T01:00:00Z", identity }); }
      if (path === "/api/observations" && init?.method === "POST") return json(observation({ observation_date: "2026-07-09" }), 201);
      if (path === "/api/birds") return json({ birds });
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Your collection" })).toBeVisible();
    expect(screen.getByText("Observed: No")).toBeVisible();
    expect(calls.filter((call) => !call.startsWith("GET "))).toEqual([]);
    await userEvent.click(screen.getByRole("button", { name: "Add to wishlist" }));
    expect(await screen.findByText("Added to wishlist.")).toBeVisible();
    expect(screen.getByText("Wishlist: Yes")).toBeVisible();
    expect(calls.some((call) => call.includes("weather") || call.includes("trip-plan") || call.includes("smtp") || call.includes("calendar"))).toBe(false);
  });

  it("suppresses unexpected non-success error fields and private server detail", async () => {
    const birds = catalog();
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/birds") return json({ birds });
      if (path === "/api/observations") return json({ observations: [] });
      if (path === "/api/life-list") return json({ birds: [] });
      if (path === "/api/wishlist") return json({ birds: [] });
      if (path === "/api/watches") return json({ watches: [] });
      if (path === "/api/wishlist/bird000" && init?.method === "PUT") return json({ error: { code: "database_busy", message: "/private/local.duckdb", detail: "secret" } }, 503);
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Wishlist" }));
    await userEvent.selectOptions(screen.getByLabelText("Add a bird"), "bird000");
    await userEvent.click(screen.getByRole("button", { name: "Add to wishlist" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The local collection is unavailable");
    expect(alert).not.toHaveTextContent("/private/local.duckdb");
    expect(alert).not.toHaveTextContent("secret");
  });

  it("rejects malformed collection payloads and hides arbitrary server details", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path === "/api/birds") return json({ birds: catalog() });
      if (path === "/api/observations") return json({ observations: [{ observation_id: "bad", private_path: "/private/secret" }] });
      if (path === "/api/life-list") return json({ birds: [] });
      if (path === "/api/wishlist") return json({ birds: [] });
      if (path === "/api/watches") return json({ watches: [] });
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Invalid local collection response");
    expect(alert).not.toHaveTextContent("/private/secret");
  });

  it("preserves new and edited observation values and focuses the error after failed saves", async () => {
    const birds = catalog();
    const existing = observation({ location: "Original location", notes: "Original note" });
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/birds") return json({ birds });
      if (path === "/api/observations" && init?.method === "POST") return json({ error: { code: "database_busy", message: "hidden" } }, 503);
      if (path === "/api/observations/obs-1" && init?.method === "PUT") return json({ error: { code: "database_busy", message: "hidden" } }, 503);
      if (path === "/api/observations") return json({ observations: [existing] });
      if (path === "/api/life-list") return json({ birds: [{ species_code: "bird000", first_observed_date: "2026-07-09", latest_observed_date: "2026-07-09", observation_count: 1, identity }] });
      if (path === "/api/wishlist") return json({ birds: [] });
      if (path === "/api/watches") return json({ watches: [] });
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Observations" }));
    const newDate = screen.getByLabelText("Observation date", { selector: "input#observation-date-new" });
    const newLocation = screen.getByLabelText(/Location \(optional personal note\)/, { selector: "input#observation-location-new" });
    const newNotes = screen.getByLabelText(/Notes \(optional\)/, { selector: "textarea#observation-notes-new" });
    await userEvent.type(newDate, "2026-07-08");
    await userEvent.type(newLocation, "Keep this location");
    await userEvent.type(newNotes, "Keep this note");
    await userEvent.click(screen.getByRole("button", { name: "Record observation" }));
    const createAlert = await screen.findByRole("alert");
    expect(createAlert).toHaveFocus();
    expect(newDate).toHaveValue("2026-07-08");
    expect(newLocation).toHaveValue("Keep this location");
    expect(newNotes).toHaveValue("Keep this note");

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const editRegion = screen.getByRole("heading", { name: /Edit Arizona Bird/ }).parentElement!;
    const editLocation = within(editRegion).getByLabelText(/Location/);
    const editNotes = within(editRegion).getByLabelText(/Notes/);
    await userEvent.clear(editLocation); await userEvent.type(editLocation, "Edited location");
    await userEvent.clear(editNotes); await userEvent.type(editNotes, "Edited note");
    await userEvent.click(within(editRegion).getByRole("button", { name: "Save changes" }));
    const editAlert = await screen.findByRole("alert");
    expect(editAlert).toHaveFocus();
    expect(screen.getByRole("heading", { name: /Edit Arizona Bird/ })).toBeVisible();
    expect(editLocation).toHaveValue("Edited location");
    expect(editNotes).toHaveValue("Edited note");
  });

  it("resets every observation edit field and update target when switching directly between rows", async () => {
    const birds = catalog();
    const secondIdentity = { ...identity, common_name: "Arizona Bird 001", scientific_name: "Avis localis1" };
    let rows = [
      observation({ observation_id: "obs-1", location: "First place", notes: "First note" }),
      observation({ observation_id: "obs-2", species_code: "bird001", observation_date: "2026-07-08", location: "Second place", notes: "Second note", identity: secondIdentity }),
    ];
    const updates: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/birds") return json({ birds });
      if (path === "/api/observations/obs-2" && init?.method === "PUT") {
        updates.push(path);
        const body = JSON.parse(String(init.body));
        rows = rows.map((row) => row.observation_id === "obs-2" ? { ...row, ...body, updated_at: "2026-07-10T02:00:00Z" } : row);
        return json(rows[1]);
      }
      if (path === "/api/observations") return json({ observations: rows });
      if (path === "/api/life-list") return json({ birds: [] });
      if (path === "/api/wishlist") return json({ birds: [] });
      if (path === "/api/watches") return json({ watches: [] });
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Observations" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    let edit = screen.getByRole("heading", { name: "Edit Arizona Bird 000" }).parentElement!;
    await userEvent.clear(within(edit).getByLabelText(/Location/));
    await userEvent.type(within(edit).getByLabelText(/Location/), "Unsaved first place");

    await userEvent.click(screen.getAllByRole("button", { name: "Edit" })[1]);
    edit = screen.getByRole("heading", { name: "Edit Arizona Bird 001" }).parentElement!;
    expect(within(edit).getByLabelText("Bird")).toHaveValue("bird001");
    expect(within(edit).getByLabelText("Observation date")).toHaveValue("2026-07-08");
    expect(within(edit).getByLabelText(/Location/)).toHaveValue("Second place");
    expect(within(edit).getByLabelText(/Notes/)).toHaveValue("Second note");
    await userEvent.click(within(edit).getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Observation updated.")).toBeVisible();
    expect(updates).toEqual(["/api/observations/obs-2"]);
  });

  it("resets watch center, radius, and update target when switching directly between rows", async () => {
    const birds = catalog();
    const secondIdentity = { ...identity, common_name: "Arizona Bird 001", scientific_name: "Avis localis1" };
    let watches = [
      watched(),
      watched({ species_code: "bird001", center_name: "Tucson, Arizona", center_latitude: 32.22, center_longitude: -110.97, radius_miles: 60, identity: secondIdentity }),
    ];
    const updates: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/birds") return json({ birds });
      if (path === "/api/observations") return json({ observations: [] });
      if (path === "/api/life-list") return json({ birds: [] });
      if (path === "/api/wishlist") return json({ birds: [] });
      if (path === "/api/watches/bird001" && init?.method === "PUT") {
        updates.push(path);
        const body = JSON.parse(String(init.body));
        watches = watches.map((row) => row.species_code === "bird001" ? { ...row, center_name: body.center.display_name, radius_miles: body.radius_miles, updated_at: "2026-07-10T02:00:00Z" } : row);
        return json(watches[1]);
      }
      if (path === "/api/watches") return json({ watches });
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Watches" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Edit center or radius" })[0]);
    let edit = screen.getByRole("heading", { name: "Edit watch for Arizona Bird 000" }).parentElement!;
    const firstRadius = within(edit).getByLabelText("Travel radius (miles)");
    await userEvent.clear(firstRadius); await userEvent.type(firstRadius, "99");

    await userEvent.click(screen.getAllByRole("button", { name: "Edit center or radius" })[1]);
    edit = screen.getByRole("heading", { name: "Edit watch for Arizona Bird 001" }).parentElement!;
    expect(within(edit).getByLabelText("Watch center")).toHaveValue("Tucson, Arizona");
    expect(within(edit).getByLabelText("Travel radius (miles)")).toHaveValue(60);
    await userEvent.click(within(edit).getByRole("button", { name: "Save watch" }));
    expect(await screen.findByText("Watch updated.")).toBeVisible();
    expect(updates).toEqual(["/api/watches/bird001"]);
  });

  it("serializes collection mutations and disables every visible mutating row control", async () => {
    const birds = catalog();
    let release: ((value: Response) => void) | undefined;
    const pending = new Promise<Response>((resolve) => { release = resolve; });
    let addCalls = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/birds") return json({ birds });
      if (path === "/api/observations") return json({ observations: [observation()] });
      if (path === "/api/life-list") return json({ birds: [{ species_code: "bird000", first_observed_date: "2026-07-09", latest_observed_date: "2026-07-09", observation_count: 1, identity }] });
      if (path === "/api/wishlist/bird000" && init?.method === "PUT") { addCalls += 1; return pending; }
      if (path === "/api/wishlist") return json({ birds: [] });
      if (path === "/api/watches") return json({ watches: [watched()] });
      throw new Error(`Unexpected request ${path}`);
    });
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Wishlist" }));
    const add = screen.getByRole("button", { name: "Add to wishlist" });
    await userEvent.click(add);
    expect(add).toBeDisabled();
    expect(addCalls).toBe(1);

    await userEvent.click(screen.getByRole("button", { name: "Observations" }));
    expect(screen.getByRole("button", { name: "Edit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete permanently" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Watches" }));
    expect(screen.getByRole("button", { name: "Edit center or radius" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Pause" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete watch" })).toBeDisabled();

    release?.(new Response(JSON.stringify({ species_code: "bird000", created_at: "2026-07-10T01:00:00Z", identity }), { status: 200, headers: { "Content-Type": "application/json" } }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Pause" })).toBeEnabled());
    expect(addCalls).toBe(1);
  });

  it("does not invalidate collection reads after a failed mutation", async () => {
    window.history.replaceState(null, "", "/birds/bird000");
    let stateReads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/birds/bird000") return json(profile());
      if (path === "/api/birds/bird000/collection-state") {
        stateReads += 1;
        return json({ species_code: "bird000", catalog_status: "current", observed: false, observation_count: 0, wishlisted: false, watched: false, watch_active: false });
      }
      if (path === "/api/wishlist/bird000" && init?.method === "PUT") return json({ error: { code: "database_busy", message: "hidden" } }, 503);
      throw new Error(`Unexpected request ${path}`);
    });

    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Add to wishlist" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("warehouse is refreshing");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(stateReads).toBe(1);
    expect(screen.getByText("Wishlist: No")).toBeVisible();
  });

  it("ignores stale collection loads across rapid route changes", async () => {
    const birds = catalog();
    let wishlistReads = 0;
    let releaseFirst: ((value: Response) => void) | undefined;
    const firstWishlist = new Promise<Response>((resolve) => { releaseFirst = resolve; });
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path === "/api/birds") return json({ birds });
      if (path === "/api/birds/bird000") return json(profile());
      if (path === "/api/birds/bird000/collection-state") return json({ species_code: "bird000", catalog_status: "current", observed: false, observation_count: 0, wishlisted: true, watched: false, watch_active: false });
      if (path === "/api/observations") return json({ observations: [] });
      if (path === "/api/life-list") return json({ birds: [] });
      if (path === "/api/watches") return json({ watches: [] });
      if (path === "/api/wishlist") {
        wishlistReads += 1;
        return wishlistReads === 1 ? firstWishlist : json({ birds: [{ species_code: "bird000", created_at: "2026-07-10T01:00:00Z", identity }] });
      }
      throw new Error(`Unexpected request ${path}`);
    });

    render(<App />);
    expect(await screen.findByRole("heading", { name: "My Birds" })).toBeVisible();
    window.history.pushState(null, "", "/birds/bird000"); window.dispatchEvent(new PopStateEvent("popstate"));
    expect(await screen.findByRole("heading", { name: "Arizona Bird 000" })).toBeVisible();
    window.history.pushState(null, "", "/my-birds"); window.dispatchEvent(new PopStateEvent("popstate"));
    await userEvent.click(await screen.findByRole("button", { name: "Wishlist" }));
    expect(await screen.findByText("Arizona Bird 000", { selector: "strong" })).toBeVisible();

    releaseFirst?.(new Response(JSON.stringify({ birds: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.getByText("Arizona Bird 000", { selector: "strong" })).toBeVisible();
    expect(wishlistReads).toBe(2);
  });

  it("keeps one mutation lock across profile-to-My-Birds navigation and component unmount", async () => {
    window.history.replaceState(null, "", "/birds/bird000");
    const birds = catalog();
    let release: ((value: Response) => void) | undefined;
    const pending = new Promise<Response>((resolve) => { release = resolve; });
    let wishlisted = false;
    let mutationCalls = 0;
    let wishlistReads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/birds/bird000") return json(profile());
      if (path === "/api/birds/bird000/collection-state") return json({ species_code: "bird000", catalog_status: "current", observed: false, observation_count: 0, wishlisted, watched: false, watch_active: false });
      if (path === "/api/wishlist/bird000" && init?.method === "PUT") { mutationCalls += 1; return pending.then((response) => { wishlisted = true; return response; }); }
      if (path === "/api/birds") return json({ birds });
      if (path === "/api/observations") return json({ observations: [] });
      if (path === "/api/life-list") return json({ birds: [] });
      if (path === "/api/wishlist") { wishlistReads += 1; return json({ birds: wishlisted ? [{ species_code: "bird000", created_at: "2026-07-10T01:00:00Z", identity }] : [] }); }
      if (path === "/api/watches") return json({ watches: [] });
      throw new Error(`Unexpected request ${path}`);
    });

    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Add to wishlist" }));
    expect(mutationCalls).toBe(1);
    await userEvent.click(screen.getByRole("link", { name: "My Birds" }));
    await userEvent.click(await screen.findByRole("button", { name: "Wishlist" }));
    const secondAdd = screen.getByRole("button", { name: "Add to wishlist" });
    expect(secondAdd).toBeDisabled();
    await userEvent.click(secondAdd);
    expect(mutationCalls).toBe(1);

    release?.(new Response(JSON.stringify({ species_code: "bird000", created_at: "2026-07-10T01:00:00Z", identity }), { status: 200, headers: { "Content-Type": "application/json" } }));
    expect(await screen.findByText("Arizona Bird 000", { selector: "strong" })).toBeVisible();
    await waitFor(() => expect(secondAdd).toBeEnabled());
    expect(mutationCalls).toBe(1);
    expect(wishlistReads).toBe(2);
  });
});
