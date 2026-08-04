import { describe, expect, it } from "vitest";
import { publicCatalogCall, publicCatalogPhoto, publicCatalogPhotos, recommendationPhoto } from "./media";

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

const inaturalistSha256 = `cd${"e".repeat(62)}`;
const inaturalistMedia = {
  ...media,
  provider: "inaturalist",
  media_id: "inaturalist-5938231789",
  url: `https://rufous-data.loughondata.com/rufous-media/v1/objects/cd/${inaturalistSha256}.webp`,
  source_url: "https://www.inaturalist.org/photos/5938231789",
  creator: "Pat Photographer",
  license: "CC BY 4.0",
  license_url: "https://creativecommons.org/licenses/by/4.0/",
  attribution_id: "inaturalist-attribution-5938231789",
  title: "Rufous Hummingbird",
  caption: null,
  sha256: inaturalistSha256,
};

const wikimediaSha256 = `ef${"0".repeat(62)}`;
const wikimediaMedia = {
  ...media,
  provider: "wikimedia",
  media_id: `wikimedia-${"1".repeat(24)}`,
  url: `https://rufous-data.loughondata.com/rufous-media/v1/objects/ef/${wikimediaSha256}.webp`,
  source_url: "https://commons.wikimedia.org/wiki/File:Abert%27s_Towhee.jpg",
  creator: "Commons Photographer",
  license: "CC BY-SA 4.0",
  license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
  attribution_id: `wikimedia-attribution-${"2".repeat(24)}`,
  scientific_name: "Melozone aberti",
  title: "Abert's Towhee",
  alt_text: "An Abert's Towhee standing on open ground",
  sha256: wikimediaSha256,
};

const audioSha256 = `12${"3".repeat(62)}`;
const xenoAudio = {
  provider: "xeno_canto",
  provider_id: "XC12345",
  source_url: "https://xeno-canto.org/12345",
  creator: "Pat Recordist",
  license: "CC BY 4.0",
  license_url: "https://creativecommons.org/licenses/by/4.0/",
  url: `https://rufous-data.loughondata.com/rufous-audio/v1/objects/12/${audioSha256}.mp3`,
  sha256: audioSha256,
  bytes: 123_456,
  mime_type: "audio/mpeg",
  duration_seconds: 42.5,
  recording_type: "call",
  modifications: "Unmodified from the credited source recording.",
  attribution_id: `audio-attribution-${audioSha256.slice(0, 24)}`,
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

describe("published iNaturalist media adapter", () => {
  it("maps a strictly attributed, exact-species R2 display copy", () => {
    const photo = publicCatalogPhoto(inaturalistMedia, "Selasphorus rufus", "2026-08-03T12:00:00Z");
    expect(photo).toMatchObject({
      status: "available",
      provider: "inaturalist",
      source_record_id: "inaturalist-5938231789",
      display_url: inaturalistMedia.url,
      source_url: "https://www.inaturalist.org/photos/5938231789",
      creator: "Pat Photographer",
      publisher: null,
      license_text: "CC BY 4.0",
      selection_reason: "Validated iNaturalist public-release photo",
    });
    expect(recommendationPhoto("Selasphorus rufus", photo)).toMatchObject({
      status: "available",
      provider: "inaturalist",
      source_record_id: "inaturalist-5938231789",
    });
  });

  it.each([
    ["non-canonical source host", { source_url: "https://inaturalist.org/photos/5938231789" }],
    ["source query", { source_url: "https://www.inaturalist.org/photos/5938231789?size=large" }],
    ["source fragment", { source_url: "https://www.inaturalist.org/photos/5938231789#photo" }],
    ["leading-zero photo id", {
      source_url: "https://www.inaturalist.org/photos/05938231789",
      media_id: "inaturalist-05938231789",
      attribution_id: "inaturalist-attribution-05938231789",
    }],
    ["mismatched media id", { media_id: "inaturalist-5938231788" }],
    ["mismatched attribution id", { attribution_id: "inaturalist-attribution-5938231788" }],
    ["older CC BY version", {
      license: "CC BY 3.0",
      license_url: "https://creativecommons.org/licenses/by/3.0/",
    }],
    ["noncommercial license", {
      license: "CC BY-NC 4.0",
      license_url: "https://creativecommons.org/licenses/by-nc/4.0/",
    }],
    ["incomplete creator credit", { creator: "" }],
    ["scientific-name mismatch", { scientific_name: "Selasphorus sasin" }],
  ])("rejects %s", (_label, change) => {
    expect(publicCatalogPhoto(
      { ...inaturalistMedia, ...change },
      "Selasphorus rufus",
      "2026-08-03T12:00:00Z",
    )).toBeNull();
  });

  it.each([
    ["CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"],
    ["CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"],
    ["CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"],
  ])("accepts the reviewed %s license", (license, licenseUrl) => {
    expect(publicCatalogPhoto({
      ...inaturalistMedia,
      license,
      license_url: licenseUrl,
    }, "Selasphorus rufus", "2026-08-03T12:00:00Z")).not.toBeNull();
  });
});

describe("published Wikimedia Commons media adapter", () => {
  it("maps a reviewed Commons File page to an immutable display copy", () => {
    const photo = publicCatalogPhoto(wikimediaMedia, "Melozone aberti", "2026-08-04T12:00:00Z");
    expect(photo).toMatchObject({
      status: "available",
      provider: "wikimedia",
      source_record_id: wikimediaMedia.media_id,
      display_url: wikimediaMedia.url,
      source_url: wikimediaMedia.source_url,
      creator: "Commons Photographer",
      publisher: null,
      license_text: "CC BY-SA 4.0",
      selection_reason: "Validated Wikimedia Commons public-release photo",
    });
    expect(recommendationPhoto("Melozone aberti", photo)).toMatchObject({
      provider: "wikimedia",
      source_record_id: wikimediaMedia.media_id,
    });
  });

  it.each([
    ["wrong source host", { source_url: "https://commons.wikimedia.org.evil.example/wiki/File:Abert%27s_Towhee.jpg" }],
    ["category instead of File page", { source_url: "https://commons.wikimedia.org/wiki/Category:Abert%27s_Towhee" }],
    ["source query", { source_url: `${wikimediaMedia.source_url}?download=1` }],
    ["encoded path separator", { source_url: "https://commons.wikimedia.org/wiki/File:Abert%2FTowhee.jpg" }],
    ["malformed media id", { media_id: "wikimedia-123" }],
    ["malformed attribution id", { attribution_id: "wikimedia-attribution-123" }],
    ["noncommercial license", {
      license: "CC BY-NC 4.0",
      license_url: "https://creativecommons.org/licenses/by-nc/4.0/",
    }],
    ["wrong public-domain URL", {
      license: "Public Domain",
      license_url: "https://creativecommons.org/publicdomain/mark/1.0/",
    }],
  ])("rejects %s", (_label, change) => {
    expect(publicCatalogPhoto(
      { ...wikimediaMedia, ...change },
      "Melozone aberti",
      "2026-08-04T12:00:00Z",
    )).toBeNull();
  });

  it.each([
    ["Public Domain", "https://commons.wikimedia.org/wiki/Commons:Copyright_tags/General_public_domain"],
    ["CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"],
    ["CC BY 2.0", "https://creativecommons.org/licenses/by/2.0/"],
    ["CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"],
  ])("accepts reviewed %s terms", (license, licenseUrl) => {
    expect(publicCatalogPhoto({
      ...wikimediaMedia,
      license,
      license_url: licenseUrl,
    }, "Melozone aberti", "2026-08-04T12:00:00Z")).not.toBeNull();
  });
});

describe("published public-audio adapter", () => {
  it("maps a content-addressed Xeno-canto recording into the existing native player contract", () => {
    expect(publicCatalogCall(xenoAudio, "Selasphorus rufus", "2026-08-04T12:00:00Z")).toMatchObject({
      status: "available",
      source_record_id: "XC12345",
      recording_id: "12345",
      species_name: "Selasphorus rufus",
      recordist: "Pat Recordist",
      source_url: "https://xeno-canto.org/12345",
      audio_url: xenoAudio.url,
      license_text: "CC BY 4.0",
      selection_reason: "Xeno-canto · Unmodified from the credited source recording.",
    });
  });

  it.each([
    ["iNaturalist", {
      provider: "inaturalist",
      provider_id: "sound-67890",
      source_url: "https://www.inaturalist.org/observations/98765",
      license: "CC0 1.0",
      license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
    }],
    ["Wikimedia Commons", {
      provider: "wikimedia",
      provider_id: "File:Rufous_Hummingbird.ogg",
      source_url: "https://commons.wikimedia.org/wiki/File:Rufous_Hummingbird.ogg",
      license: "CC BY-SA 4.0",
      license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
    }],
    ["USFWS", {
      provider: "usfws",
      provider_id: "lesser-scaup-audio",
      source_url: "https://www.fws.gov/media/lesser-scaup-audio",
      license: "Public Domain",
      license_url: "https://www.fws.gov/notices",
    }],
  ])("accepts an exact %s recording source and commercial-safe license", (_label, identity) => {
    expect(publicCatalogCall(
      { ...xenoAudio, ...identity },
      "Selasphorus rufus",
      "2026-08-04T12:00:00Z",
    )).not.toBeNull();
  });

  it.each([
    ["direct provider download instead of R2", { url: "https://xeno-canto.org/12345/download" }],
    ["wrong R2 namespace", { url: xenoAudio.url.replace("rufous-audio", "rufous-media") }],
    ["wrong hash shard", { url: xenoAudio.url.replace("/objects/12/", "/objects/ff/") }],
    ["hash mismatch", { sha256: "4".repeat(64) }],
    ["MIME/extension mismatch", { mime_type: "audio/ogg" }],
    ["source query", { source_url: "https://xeno-canto.org/12345?download=1" }],
    ["provider ID mismatch", { provider_id: "XC54321" }],
    ["noncommercial license", {
      license: "CC BY-NC 4.0",
      license_url: "https://creativecommons.org/licenses/by-nc/4.0/",
    }],
    ["wrong attribution identity", { attribution_id: "audio-attribution-000000000000000000000000" }],
    ["empty creator", { creator: "" }],
    ["oversized object", { bytes: 25 * 1024 * 1024 + 1 }],
    ["excessive duration", { duration_seconds: 3_600.1 }],
    ["unexpected field", { private_note: "must not enter the browser contract" }],
  ])("rejects %s", (_label, mutation) => {
    expect(publicCatalogCall(
      { ...xenoAudio, ...mutation },
      "Selasphorus rufus",
      "2026-08-04T12:00:00Z",
    )).toBeNull();
  });

  it("keeps a missing species attachment unavailable", () => {
    expect(publicCatalogCall(xenoAudio, null, "2026-08-04T12:00:00Z")).toBeNull();
  });
});
