import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  PublicCreditsPage,
  safeAttributionHref,
  safeDoiHref,
  safeItemSourceHref,
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
    media_source: "usfws+inaturalist",
    media_delivery: "immutable_r2",
  },
  license_policy: {
    version: 1,
    allowed: { gbif: ["CC BY 4.0"] },
    rejected_counts: {},
  },
  counts: {
    species: 12,
    observations: 3000,
    places: 500,
    attribution_items: 2,
    media_items: 1,
    species_with_media: 1,
  },
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
    {
      provider: "inaturalist",
      title: "iNaturalist",
      url: "https://www.inaturalist.org/",
      license: "Per-item Creative Commons license",
      license_url: null,
      credit: "Individual creators are credited on each media item.",
    },
  ],
  items: [
    {
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
    },
    {
      attribution_id: "inaturalist-attribution-5938231789",
      provider: "inaturalist",
      source_url: "https://www.inaturalist.org/photos/5938231789",
      creator: "Pat Photographer",
      license: "CC BY-SA 4.0",
      license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
    },
  ],
};

afterEach(cleanup);

describe("public credits", () => {
  it("stacks every credits section in one content column", () => {
    expect(styles).toMatch(/\.credits-main\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s);
    expect(styles).toMatch(/\.credit-release\s*\{[^}]*max-width:\s*none/s);
    expect(styles).toMatch(/\.credits-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s);
    expect(styles).not.toMatch(/\.credits-grid\s*\{[^}]*repeat\(2,/s);
    expect(styles).toMatch(/\.credit-items ul\s*\{[^}]*max-height:\s*min\(52dvh, 520px\);[^}]*overflow-y:\s*auto/s);
  });

  it("renders the production provider, license, modifications, disclaimer, citation, and GNIS credit", async () => {
    const loadManifest = vi.fn().mockResolvedValue(manifest);
    const loadAttribution = vi.fn().mockResolvedValue(attribution);
    render(<PublicCreditsPage loadManifest={loadManifest} loadAttribution={loadAttribution} />);

    expect(await screen.findByRole("heading", { name: "Credits and data sources", level: 1 })).toBeVisible();
    expect(screen.getByText(/licensed historical GBIF occurrences/)).toBeVisible();
    expect(screen.getByText(/U\.S\. Fish and Wildlife Service and iNaturalist creators/)).toBeVisible();
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
    const inaturalist = screen.getByRole("heading", { name: "iNaturalist", level: 2 }).closest("article");
    expect(inaturalist).not.toBeNull();
    expect(within(inaturalist!).getByText("Individual creators are credited on each media item.")).toBeVisible();
    expect(screen.getByText("Creator: Pat Photographer")).toBeVisible();
    expect(screen.getByRole("link", { name: "Open cited source on inaturalist.org" })).toHaveAttribute(
      "href",
      "https://www.inaturalist.org/photos/5938231789",
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

  it.each([
    ["inaturalist", "https://www.inaturalist.org/photos/5938231789", "https://www.inaturalist.org/photos/5938231789"],
    ["inaturalist", "https://www.inaturalist.org/photos/5938231789?size=large", null],
    ["inaturalist", "https://inaturalist.org/photos/5938231789", null],
    ["inaturalist", "https://www.inaturalist.org/photos/0", null],
    ["wikimedia", "https://commons.wikimedia.org/wiki/File:Abert%27s_Towhee.jpg", "https://commons.wikimedia.org/wiki/File:Abert%27s_Towhee.jpg"],
    ["wikimedia", "https://commons.wikimedia.org/wiki/File:Abert%27s_Towhee.jpg?download=1", null],
    ["wikimedia", "https://commons.wikimedia.org/wiki/Category:Abert%27s_Towhee", null],
    ["wikimedia", "https://commons.wikimedia.org/wiki/File:Abert%2FTowhee.jpg", null],
    ["xeno_canto", "https://xeno-canto.org/12345", "https://xeno-canto.org/12345"],
    ["xeno_canto", "https://xeno-canto.org/12345/download", null],
    ["inaturalist", "https://www.inaturalist.org/observations/98765", "https://www.inaturalist.org/observations/98765"],
    ["inaturalist", "https://www.inaturalist.org/observations/98765?view=sounds", null],
    ["gbif", "https://www.gbif.org/dataset/example", "https://www.gbif.org/dataset/example"],
  ])("enforces an exact per-photo source URL for %s: %s", (provider, value, expected) => {
    expect(safeItemSourceHref(provider, value)).toBe(expected);
  });

  it("credits Wikimedia Commons creators and links each exact File page", async () => {
    const commonsManifest = structuredClone(manifest);
    commonsManifest.source_policy.media_source = "usfws+inaturalist+wikimedia";
    const commonsAttribution = structuredClone(attribution);
    commonsAttribution.sources.push({
      provider: "wikimedia",
      title: "Wikimedia Commons",
      url: "https://commons.wikimedia.org/",
      license: "Per-item Public Domain or Creative Commons license",
      license_url: null,
      credit: "Individual creators are credited on each media item.",
      modifications: "Rufous resized and re-encoded reviewed web display copies.",
    });
    commonsAttribution.items.push({
      attribution_id: `wikimedia-attribution-${"2".repeat(24)}`,
      provider: "wikimedia",
      source_url: "https://commons.wikimedia.org/wiki/File:Abert%27s_Towhee.jpg",
      creator: "Commons Photographer",
      license: "CC BY-SA 4.0",
      license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
    });
    render(<PublicCreditsPage
      loadManifest={vi.fn().mockResolvedValue(commonsManifest)}
      loadAttribution={vi.fn().mockResolvedValue(commonsAttribution)}
    />);

    expect(await screen.findByText(/Wikimedia Commons creators/)).toBeVisible();
    const commons = screen.getByRole("heading", { name: "Wikimedia Commons", level: 2 }).closest("article");
    expect(commons).not.toBeNull();
    expect(within(commons!).getByText("Individual creators are credited on each media item.")).toBeVisible();
    expect(screen.getByText("Creator: Commons Photographer")).toBeVisible();
    expect(screen.getByRole("link", { name: "Open cited source on commons.wikimedia.org" })).toHaveAttribute(
      "href",
      "https://commons.wikimedia.org/wiki/File:Abert%27s_Towhee.jpg",
    );
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

  it("reports public-audio coverage and renders exact per-recording attribution", async () => {
    const audioManifest = structuredClone(manifest);
    audioManifest.source_policy.audio_source = "xeno_canto+inaturalist+wikimedia+usfws";
    audioManifest.source_policy.audio_delivery = "immutable_r2";
    audioManifest.counts.audio_items = 199;
    audioManifest.counts.species_with_audio = 199;
    const audioAttribution = structuredClone(attribution);
    audioAttribution.sources.push({
      provider: "xeno_canto",
      title: "Xeno-canto",
      url: "https://xeno-canto.org/",
      license: "Per-recording Creative Commons license",
      license_url: null,
      credit: "Recordists are credited beside every published sound.",
    });
    audioAttribution.items.push({
      attribution_id: `audio-attribution-${"ef"}${"4".repeat(22)}`,
      kind: "audio",
      provider: "xeno_canto",
      provider_id: "XC12345",
      source_url: "https://xeno-canto.org/12345",
      creator: "Pat Recordist",
      license: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
      common_name: "Rufous Hummingbird",
      scientific_name: "Selasphorus rufus",
      recording_type: "call",
      modifications: "Unmodified from the credited source recording.",
    });
    render(<PublicCreditsPage
      loadManifest={vi.fn().mockResolvedValue(audioManifest)}
      loadAttribution={vi.fn().mockResolvedValue(audioAttribution)}
    />);

    expect(await screen.findByText(/199 commercially reusable bird sounds/)).toHaveTextContent(
      "Xeno-canto, iNaturalist, Wikimedia Commons, and USFWS",
    );
    expect(screen.getByText(/199 bird sounds$/)).toBeVisible();
    expect(screen.getByText("Creator: Pat Recordist")).toBeVisible();
    expect(screen.getByText("Recording: XC12345")).toBeVisible();
    expect(screen.getByText("Species:")).toHaveTextContent("Selasphorus rufus");
    expect(screen.getByText("Changes: Unmodified from the credited source recording.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Open cited source on xeno-canto.org" })).toHaveAttribute(
      "href", "https://xeno-canto.org/12345",
    );
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
