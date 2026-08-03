import { describe, expect, it } from "vitest";
import { publicCatalogPhoto, publicCatalogPhotos, recommendationPhoto } from "./media";

const sha256 = `ab${"c".repeat(62)}`;
const media = {
  kind: "photo",
  provider: "usfws",
  media_id: "rufous-hummingbird-perched",
  url: `https://rufous-data.loughondata.com/rufous-media/v1/objects/ab/${sha256}.webp`,
  source_url: "https://www.fws.gov/media/rufous-hummingbird-perched",
  creator: "Jane Birder/USFWS",
  license: "Public Domain",
  license_url: "https://www.fws.gov/notices",
  attribution_id: "usfws-rufous-1",
  scientific_name: "Selasphorus rufus",
  title: "Rufous Hummingbird perched on a twig",
  caption: "Photographed at a national wildlife refuge.",
  alt_text: "A Rufous Hummingbird perched on a narrow twig",
  width: 650,
  height: 488,
  mime_type: "image/webp",
  sha256,
};

describe("published USFWS media adapter", () => {
  it("maps an exact content-addressed public photo into catalog presentation data", () => {
    expect(publicCatalogPhoto(media, "Selasphorus rufus", "2026-08-03T12:00:00Z")).toMatchObject({
      status: "available",
      provider: "usfws",
      display_url: media.url,
      source_url: media.source_url,
      creator: media.creator,
      license_text: "Public Domain",
      license_url: "https://www.fws.gov/notices",
      alt_text: media.alt_text,
      media_title: media.title,
      caption: media.caption,
    });
  });

  it("adapts a validated catalog photo to the exact trip recommendation contract", () => {
    const catalogPhoto = publicCatalogPhoto(media, "Selasphorus rufus", "2026-08-03T12:00:00Z");
    const recommendation = recommendationPhoto("Selasphorus rufus", catalogPhoto);
    expect(recommendation).toMatchObject({
      status: "available",
      provider: "usfws",
      species_name: "Selasphorus rufus",
      source_record_id: media.media_id,
      source_url: media.source_url,
    });
    expect(recommendation).not.toHaveProperty("lookup_at");
    expect(recommendation).not.toHaveProperty("alt_text");
    expect(recommendation).not.toHaveProperty("media_title");
    expect(recommendation).not.toHaveProperty("caption");
    expect(recommendation).not.toHaveProperty("attribution_id");
  });

  it("falls closed when adapting a mismatched catalog photo", () => {
    const catalogPhoto = publicCatalogPhoto(media, "Selasphorus rufus", "2026-08-03T12:00:00Z");
    expect(recommendationPhoto("Selasphorus sasin", catalogPhoto)).toMatchObject({
      status: "unavailable",
      provider: null,
      species_name: null,
    });
  });

  it("accepts safe consecutive hyphens in an official USFWS media slug", () => {
    const sourceUrl = "https://www.fws.gov/media/rufous--hummingbird";
    expect(publicCatalogPhoto(
      { ...media, source_url: sourceUrl },
      "Selasphorus rufus",
      "2026-08-03T12:00:00Z",
    )).toMatchObject({ source_url: sourceUrl, provider: "usfws" });
  });

  it.each([
    ["wrong media host", { url: media.url.replace("rufous-data.loughondata.com", "example.com") }],
    ["wrong hash shard", { url: media.url.replace("/objects/ab/", "/objects/ff/") }],
    ["wrong source host", { source_url: "https://example.com/media/rufous-hummingbird" }],
    ["unsafe source slug", { source_url: "https://www.fws.gov/media/../notices" }],
    ["species mismatch", { scientific_name: "Selasphorus sasin" }],
    ["hash mismatch", { sha256: "d".repeat(64) }],
    ["MIME mismatch", { mime_type: "image/jpeg" }],
    ["noncommercial license", { license: "CC BY-NC 4.0", license_url: "https://creativecommons.org/licenses/by-nc/4.0/" }],
    ["unofficial public-domain URL", { license_url: "https://www.fws.gov/media/rufous-hummingbird-perched" }],
    ["missing credit", { creator: "" }],
    ["markup in alt text", { alt_text: "<img src=x>" }],
  ])("rejects %s", (_label, change) => {
    expect(publicCatalogPhoto({ ...media, ...change }, "Selasphorus rufus", "2026-08-03T12:00:00Z")).toBeNull();
  });

  it("accepts canonical allowed Creative Commons terms and deduplicates repeated media", () => {
    const cc = {
      ...media,
      license: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
    };
    expect(publicCatalogPhotos([cc, cc, { ...cc, media_id: "bad", source_url: "https://example.com" }], "Selasphorus rufus", "2026-08-03T12:00:00Z"))
      .toHaveLength(1);
    expect(publicCatalogPhoto({
      ...media,
      license: "CC BY-SA 2.5",
      license_url: "https://creativecommons.org/licenses/by-sa/2.5/",
    }, "Selasphorus rufus", "2026-08-03T12:00:00Z")).not.toBeNull();
  });

  it("accepts the publisher's full alt-text contract and rejects larger values", () => {
    expect(publicCatalogPhoto(
      { ...media, alt_text: "A".repeat(1_000) },
      "Selasphorus rufus",
      "2026-08-03T12:00:00Z",
    )).not.toBeNull();
    expect(publicCatalogPhoto(
      { ...media, alt_text: "A".repeat(1_001) },
      "Selasphorus rufus",
      "2026-08-03T12:00:00Z",
    )).toBeNull();
  });
});
