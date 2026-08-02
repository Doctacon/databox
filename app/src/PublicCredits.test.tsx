import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  PublicCreditsPage,
  safeAttributionHref,
  safeDoiHref,
} from "./PublicCredits";
import type { PublicAttribution, PublicManifest } from "./publicTypes";
import styles from "./styles.css?raw";

const manifest: PublicManifest = {
  schema_version: 1,
  mode: "public",
  release_mode: "production",
  generated_at: "2026-08-02T12:00:00Z",
  data_version: "a".repeat(64),
  region: {
    code: "US-AZ",
    name: "Arizona",
    bounds: { west: -114.82, south: 31.33, east: -109.04, north: 37.01 },
  },
  species: [],
  cells: [],
  place_prefixes: [],
  attribution_path: "/data/attribution.json",
  source_policy: {
    direct_ebird: "excluded",
    occurrence_source: "gbif",
    gbif_dataset_key: "4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
    coverage: "bounded_sample",
    required_taxon_key: 2476855,
  },
  license_policy: {
    version: 1,
    allowed: { gbif: ["CC BY 4.0"] },
    rejected_counts: {},
  },
  counts: { species: 12, observations: 3000, places: 500, attribution_items: 1 },
};

const attribution: PublicAttribution = {
  schema_version: 1,
  generated_at: "2026-08-02T12:00:00Z",
  sources: [
    {
      provider: "gbif_ebird_eod",
      title: "EOD – eBird Observation Dataset",
      url: "https://www.gbif.org/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
      license: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
      credit: "Cornell Lab of Ornithology, EOD – eBird Observation Dataset, accessed through GBIF.org.",
      modifications: "Rufous selected Arizona records, removed observer fields, rounded coordinates to 0.01°, and grouped occurrences into static grid cells.",
      disclaimer: "No warranty either expressed or implied is made regarding the accuracy of these data.",
    },
    {
      provider: "usgs_gnis",
      title: "Geographic Names Information System",
      url: "https://www.usgs.gov/us-board-on-geographic-names/download-gnis-data",
      license: "U.S. Government public domain",
      license_url: null,
      credit: `U.S. Geological Survey; pinned snapshot SHA-256 ${"b".repeat(64)}`,
    },
  ],
  items: [{
    attribution_id: "gbif-eod-citation",
    provider: "gbif",
    source_url: "https://www.gbif.org/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
    creator: "Cornell Lab of Ornithology",
    license: "CC BY 4.0",
    license_url: "https://creativecommons.org/licenses/by/4.0/",
    dataset_title: "EOD – eBird Observation Dataset",
    publisher: "Cornell Lab of Ornithology",
    dataset_citation: "Cornell Lab of Ornithology. EOD – eBird Observation Dataset.",
    dataset_doi: "10.15468/aomfnb",
  }],
};

afterEach(cleanup);

describe("public credits", () => {
  it("stacks every credits section in one content column", () => {
    expect(styles).toMatch(/\.credits-main\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s);
    expect(styles).toMatch(/\.credit-release\s*\{[^}]*max-width:\s*none/s);
    expect(styles).toMatch(/\.credits-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s);
    expect(styles).not.toMatch(/\.credits-grid\s*\{[^}]*repeat\(2,/s);
  });

  it("renders the production provider, license, modifications, disclaimer, citation, and GNIS credit", async () => {
    const loadManifest = vi.fn().mockResolvedValue(manifest);
    const loadAttribution = vi.fn().mockResolvedValue(attribution);
    render(<PublicCreditsPage loadManifest={loadManifest} loadAttribution={loadAttribution} />);

    expect(await screen.findByRole("heading", { name: "Credits and data sources", level: 1 })).toBeVisible();
    expect(screen.getByText(/licensed historical GBIF occurrences/)).toBeVisible();
    const eod = screen.getByRole("heading", { name: "EOD – eBird Observation Dataset", level: 2 }).closest("article");
    expect(eod).not.toBeNull();
    expect(within(eod!).getByText("gbif_ebird_eod")).toBeVisible();
    expect(within(eod!).getByText(/Cornell Lab of Ornithology.*accessed through GBIF\.org/)).toBeVisible();
    expect(eod).toHaveTextContent(/Changes made by Rufous:.*rounded coordinates to 0\.01°/);
    expect(eod).toHaveTextContent(/Source notice:.*No warranty either expressed or implied/);
    expect(within(eod!).getByRole("link", { name: "CC BY 4.0" })).toHaveAttribute(
      "href",
      "https://creativecommons.org/licenses/by/4.0/",
    );
    expect(within(eod!).getByRole("link", { name: /Open provider source on gbif\.org/ })).toHaveAttribute(
      "rel",
      "noreferrer",
    );

    const gnis = screen.getByRole("heading", { name: "Geographic Names Information System", level: 2 }).closest("article");
    expect(gnis).not.toBeNull();
    expect(within(gnis!).getByText(new RegExp(`pinned snapshot SHA-256 ${"b".repeat(64)}`))).toBeVisible();
    expect(screen.getByText("Recommended citation: Cornell Lab of Ornithology. EOD – eBird Observation Dataset.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Dataset DOI: 10.15468/aomfnb" })).toHaveAttribute(
      "href",
      "https://doi.org/10.15468/aomfnb",
    );
    expect(loadAttribution).toHaveBeenCalledWith("/data/attribution.json", expect.any(AbortSignal));
  });

  it.each([
    ["javascript:alert(1)", null],
    ["data:text/html,hello", null],
    ["http://www.gbif.org/dataset/1", null],
    ["https://user@www.gbif.org/dataset/1", null],
    ["https://www.gbif.org:444/dataset/1", null],
    ["https://www.gbif.org\\@evil.example/dataset/1", null],
    [" https://www.gbif.org/dataset/1", null],
    ["https://www.gbif.org/dataset/1?view=table", "https://www.gbif.org/dataset/1?view=table"],
  ])("validates an external attribution URL before linking: %s", (value, expected) => {
    expect(safeAttributionHref(value)).toBe(expected);
  });

  it("keeps unsafe persisted URLs inert while preserving their attribution text", async () => {
    const unsafe = structuredClone(attribution);
    unsafe.sources = [{
      ...unsafe.sources[0],
      url: "javascript:alert(1)",
      license_url: "http://creativecommons.org/licenses/by/4.0/",
    }];
    unsafe.items[0].source_url = "https://user@www.gbif.org/dataset/1";
    unsafe.items[0].license_url = "data:text/html,not-a-license";
    unsafe.items[0].dataset_doi = " 10.15468/aomfnb";
    render(<PublicCreditsPage
      loadManifest={vi.fn().mockResolvedValue(manifest)}
      loadAttribution={vi.fn().mockResolvedValue(unsafe)}
    />);

    await screen.findByRole("heading", { name: "EOD – eBird Observation Dataset", level: 2 });
    expect(screen.getByText("Provider source link unavailable.")).toBeVisible();
    expect(screen.getByText("Cited source link unavailable.")).toBeVisible();
    expect(screen.getByText((_, element) => element?.textContent === "License: CC BY 4.0")).toBeVisible();
    expect(screen.getByText("CC BY 4.0")).toBeVisible();
    expect(screen.queryByRole("link", { name: "CC BY 4.0" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Dataset DOI/ })).not.toBeInTheDocument();
    expect(document.querySelector('a[href^="javascript:"]')).not.toBeInTheDocument();
    expect(document.querySelector('a[href^="data:"]')).not.toBeInTheDocument();
    expect(document.querySelector('a[href^="http:"]')).not.toBeInTheDocument();
  });

  it.each([
    ["10.15468/aomfnb", "https://doi.org/10.15468/aomfnb"],
    [" 10.15468/aomfnb", null],
    ["https://doi.org/10.15468/aomfnb", null],
    ["10.15468/aomfnb%0Ajavascript:alert(1)", null],
  ])("validates a DOI before constructing a link: %s", (value, expected) => {
    expect(safeDoiHref(value)).toBe(expected);
  });
});
