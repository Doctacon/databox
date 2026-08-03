import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PublicApp from "./PublicApp";
import publicStyles from "./publicStyles.css?raw";
import { PUBLIC_WATCH_STORAGE_KEY } from "./publicWatch";
import manifest from "../public/data/manifest.json";
import attribution from "../public/data/attribution.json";
import gilwoo from "../public/data/species/gilwoo.json";
import mexjay from "../public/data/species/mexjay.json";
import rufhum from "../public/data/species/rufhum.json";
import n34w113 from "../public/data/cells/n34w113.json";
import prescott from "../public/data/places/pr.json";

function json(value: unknown) {
  return Promise.resolve(new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } }));
}

function mockFixtureFetch(attributionFixture: unknown = attribution) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url === "/data/manifest.json") return json(manifest);
    if (url === "/data/attribution.json") return json(attributionFixture);
    if (url === "/data/species/gilwoo.json") return json(gilwoo);
    if (url === "/data/species/mexjay.json") return json(mexjay);
    if (url === "/data/species/rufhum.json") return json(rufhum);
    if (url === "/data/places/pr.json") return json(prescott);
    if (url === "/data/cells/n34w113.json") return json(n34w113);
    return Promise.resolve(new Response("not found", { status: 404 }));
  });
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("Rufous public app", () => {
  it("keeps the complete licensed bird photo visible in its species profile", () => {
    expect(publicStyles).toMatch(/\.public-profile-media\s*>\s*img[^}]*object-fit:\s*contain;[^}]*object-position:\s*center/s);
  });

  it("builds, saves, evaluates, maps, and downloads a watch without collecting email", async () => {
    const fetchMock = mockFixtureFetch();
    let clickedAnchor: HTMLAnchorElement | null = null;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function captureDownload(this: HTMLAnchorElement) {
      clickedAnchor = this;
    });

    const user = userEvent.setup();
    render(<PublicApp />);
    expect(await screen.findByRole("heading", { name: /Watch for an Arizona bird/ })).toBeVisible();
    expect(document.querySelector('input[type="email"]')).toBeNull();
    expect(screen.getByText(/never asks for your email/i)).toBeVisible();

    await user.selectOptions(screen.getByLabelText("Bird"), "mexjay");
    const outingDate = (screen.getByLabelText("Outing date") as HTMLInputElement).value;
    await user.type(screen.getByLabelText("Arizona place or coordinates"), "Prescott");
    await user.click(await screen.findByRole("button", { name: /Prescott, Arizona/ }));
    await user.click(screen.getByRole("button", { name: "Evaluate and save on this device" }));

    expect(await screen.findByText(/Rufous found a licensed historical Mexican Jay occurrence/)).toBeVisible();
    expect(screen.getByRole("img", { name: /Arizona watch evidence map/ })).toBeVisible();
    expect(document.querySelector("path.public-map-region")).toHaveAttribute("d", expect.stringContaining("M"));
    expect(screen.getByText(/1 current static match/)).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith("/data/cells/n34w113.json", expect.objectContaining({ credentials: "omit" }));
    const stored = localStorage.getItem(PUBLIC_WATCH_STORAGE_KEY);
    expect(stored).toContain("mexjay");
    expect(stored).not.toMatch(/email/i);

    await user.click(screen.getByRole("button", { name: "Download calendar event (.ics)" }));
    expect(clickedAnchor).not.toBeNull();
    expect(clickedAnchor!.download).toBe(`rufous-mexjay-${outingDate}.ics`);
    expect(clickedAnchor!.href).toBe("blob:local-maplibre-worker");
  });

  it("asks for a time convention for manual coordinates and makes no runtime service request", async () => {
    const fetchMock = mockFixtureFetch();
    const user = userEvent.setup();
    render(<PublicApp />);
    await screen.findByRole("heading", { name: /Watch for an Arizona bird/ });
    await user.type(screen.getByLabelText("Arizona place or coordinates"), "34.54,-112.47");

    const selector = await screen.findByLabelText("Time convention for these coordinates");
    expect(selector).toBeRequired();
    expect(screen.getByText(/static site cannot look up a time zone/)).toBeVisible();
    await user.selectOptions(selector, "America/Denver");
    await user.click(screen.getByRole("button", { name: "Evaluate and save on this device" }));

    const stored = JSON.parse(localStorage.getItem(PUBLIC_WATCH_STORAGE_KEY) ?? "[]") as Array<{ center_timezone: string }>;
    expect(stored[0].center_timezone).toBe("America/Denver");
    expect(fetchMock.mock.calls.every(([input]) => String(input).startsWith("/data/"))).toBe(true);
    expect(document.querySelector('script[src*="turnstile"]')).toBeNull();
  });

  it("visibly renders the GBIF citation, DOI, license, and Rufous modification notice", async () => {
    mockFixtureFetch({
      ...attribution,
      sources: [{
        provider: "gbif_ebird_eod",
        title: "EOD – eBird Observation Dataset",
        url: "https://www.gbif.org/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        license: "CC BY 4.0",
        license_url: "https://creativecommons.org/licenses/by/4.0/",
        credit: "Cornell Lab of Ornithology, accessed through GBIF.org.",
        modifications: "Rufous selected Arizona records and rounded coordinates to 0.01°.",
        disclaimer: "No warranty either expressed or implied is made regarding the accuracy of these data.",
      }],
      items: [{
        attribution_id: "gbif-credit",
        provider: "gbif",
        creator: "Cornell Lab of Ornithology",
        source_url: "https://www.gbif.org/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        license: "CC BY 4.0",
        license_url: "https://creativecommons.org/licenses/by/4.0/",
        dataset_title: "EOD – eBird Observation Dataset",
        dataset_key: "4fa7b334-ce0d-4e88-aaae-2e0c138d049e",
        publisher: "Cornell Lab of Ornithology",
        dataset_citation: "Full recommended EOD dataset citation.",
        dataset_doi: "10.15468/aomfnb",
      }],
    });

    render(<PublicApp />);

    expect(await screen.findByText(/Changes made by Rufous: Rufous selected Arizona records/)).toBeVisible();
    expect(screen.getByText(/Source notice: No warranty either expressed or implied/)).toBeVisible();
    expect(screen.getByText("Recommended citation: Full recommended EOD dataset citation.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Dataset DOI: 10.15468/aomfnb" })).toHaveAttribute(
      "href",
      "https://doi.org/10.15468/aomfnb",
    );
    expect(screen.getAllByRole("link", { name: "CC BY 4.0" })).toHaveLength(2);
  });
});
