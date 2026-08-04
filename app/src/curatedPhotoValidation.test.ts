import { describe, expect, it } from "vitest";
import { validateAvailableCuratedPhoto } from "./curatedPhotoValidation";

const photo = {
  status: "available", source_record_id: "42", species_name: "Trogon elegans",
  display_url: "https://inaturalist-open-data.s3.amazonaws.com/photos/42/large.jpg",
  source_url: "https://www.inaturalist.org/photos/42", creator: "Ada Birder",
  rights_holder: null, publisher: null, format: null, license_text: "CC BY-SA 4.0",
  license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
  selection_reason: "First eligible photo in curated iNaturalist shortlist position 1",
  provider: "inaturalist", license_code: "CC BY-SA 4.0", original_width: 1600,
  original_height: 1200, caveats: [],
};

const usfwsHash = `ab${"c".repeat(62)}`;
const usfwsPhoto = {
  status: "available", source_record_id: "usfws-rufous-1", species_name: "Selasphorus rufus",
  display_url: `https://rufous-data.loughondata.com/rufous-media/v1/objects/ab/${usfwsHash}.webp`,
  source_url: "https://www.fws.gov/media/rufous--hummingbird", creator: "USFWS Photographer",
  rights_holder: null, publisher: "U.S. Fish and Wildlife Service", format: "image/webp",
  license_text: "Public Domain", license_url: "https://www.fws.gov/notices",
  selection_reason: "Validated USFWS public-release photo", provider: "usfws",
  license_code: "Public Domain", original_width: 650, original_height: 488, caveats: [],
};

const inaturalistHash = `cd${"e".repeat(62)}`;
const publishedInaturalistPhoto = {
  status: "available", source_record_id: "inaturalist-5938231789", species_name: "Selasphorus rufus",
  display_url: `https://rufous-data.loughondata.com/rufous-media/v1/objects/cd/${inaturalistHash}.webp`,
  source_url: "https://www.inaturalist.org/photos/5938231789", creator: "Pat Photographer",
  rights_holder: null, publisher: null, format: "image/webp",
  license_text: "CC BY-SA 4.0", license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
  selection_reason: "Validated iNaturalist public-release photo", provider: "inaturalist",
  license_code: "CC BY-SA 4.0", original_width: 650, original_height: 488, caveats: [],
};

const wikimediaHash = `ef${"0".repeat(62)}`;
const publishedWikimediaPhoto = {
  status: "available", source_record_id: `wikimedia-${"1".repeat(24)}`, species_name: "Melozone aberti",
  display_url: `https://rufous-data.loughondata.com/rufous-media/v1/objects/ef/${wikimediaHash}.webp`,
  source_url: "https://commons.wikimedia.org/wiki/File:Abert%27s_Towhee.jpg", creator: "Commons Photographer",
  rights_holder: null, publisher: null, format: "image/webp",
  license_text: "CC BY 2.5", license_url: "https://creativecommons.org/licenses/by/2.5/",
  selection_reason: "Validated Wikimedia Commons public-release photo", provider: "wikimedia",
  license_code: "CC BY 2.5", original_width: 650, original_height: 488, caveats: [],
};

describe("curated iNaturalist photo validation", () => {
  it("accepts an exact safe provider result", () => {
    expect(validateAvailableCuratedPhoto(photo, "Trogon elegans")).toMatchObject({
      providerLabel: "iNaturalist", sourceUrl: photo.source_url, displayUrl: photo.display_url,
    });
  });

  it.each([
    ["legacy provider", { provider: "wikimedia_commons" }],
    ["wrong display host", { display_url: "https://evil.example/photos/42/large.jpg" }],
    ["wrong photo identity", { display_url: "https://inaturalist-open-data.s3.amazonaws.com/photos/41/large.jpg" }],
    ["original variant", { display_url: "https://inaturalist-open-data.s3.amazonaws.com/photos/42/original.jpg" }],
    ["explicit port", { source_url: "https://www.inaturalist.org:443/photos/42" }],
    ["credentials", { source_url: "https://user@www.inaturalist.org/photos/42" }],
    ["query", { source_url: "https://www.inaturalist.org/photos/42?x=1" }],
    ["fragment", { source_url: "https://www.inaturalist.org/photos/42#x" }],
    ["unsupported license", { license_text: "CC BY-ND 4.0", license_code: "CC BY-ND 4.0", license_url: "https://creativecommons.org/licenses/by-nd/4.0/" }],
    ["invented version", { license_text: "CC BY 9.0", license_code: "CC BY 9.0", license_url: "https://creativecommons.org/licenses/by/9.0/" }],
    ["noncanonical license", { license_url: "https://www.creativecommons.org/licenses/by-sa/4.0/" }],
    ["undersized", { original_width: 900, original_height: 900 }],
  ])("rejects %s", (_name, change) => {
    expect(validateAvailableCuratedPhoto({ ...photo, ...change }, "Trogon elegans")).toBeNull();
  });
});

describe("published USFWS recommendation photo validation", () => {
  it("accepts a content-addressed public photo and consecutive-hyphen source slug", () => {
    expect(validateAvailableCuratedPhoto(usfwsPhoto, "Selasphorus rufus")).toMatchObject({
      providerLabel: "USFWS",
      sourceUrl: usfwsPhoto.source_url,
      displayUrl: usfwsPhoto.display_url,
      licenseCode: "Public Domain",
    });
  });

  it.each([
    ["wrong media host", { display_url: usfwsPhoto.display_url.replace("rufous-data.loughondata.com", "example.com") }],
    ["wrong hash shard", { display_url: usfwsPhoto.display_url.replace("/objects/ab/", "/objects/cd/") }],
    ["unsafe source slug", { source_url: "https://www.fws.gov/media/rufous-" }],
    ["wrong publisher", { publisher: "Unknown" }],
    ["oversized derivative", { original_width: 651 }],
    ["noncommercial license", { license_text: "CC BY-NC 4.0", license_code: "CC BY-NC 4.0", license_url: "https://creativecommons.org/licenses/by-nc/4.0/" }],
  ])("rejects %s", (_name, change) => {
    expect(validateAvailableCuratedPhoto({ ...usfwsPhoto, ...change }, "Selasphorus rufus")).toBeNull();
  });
});

describe("published iNaturalist recommendation photo validation", () => {
  it("accepts only the content-addressed display copy tied to the exact source photo", () => {
    expect(validateAvailableCuratedPhoto(publishedInaturalistPhoto, "Selasphorus rufus")).toMatchObject({
      providerLabel: "iNaturalist",
      sourceUrl: publishedInaturalistPhoto.source_url,
      displayUrl: publishedInaturalistPhoto.display_url,
      licenseCode: "CC BY-SA 4.0",
    });
  });

  it.each([
    ["live upstream image", { display_url: "https://inaturalist-open-data.s3.amazonaws.com/photos/5938231789/large.jpg" }],
    ["mismatched source record", { source_record_id: "inaturalist-5938231788" }],
    ["source query", { source_url: "https://www.inaturalist.org/photos/5938231789?x=1" }],
    ["oversized derivative", { original_height: 651 }],
    ["older license", {
      license_text: "CC BY 3.0",
      license_code: "CC BY 3.0",
      license_url: "https://creativecommons.org/licenses/by/3.0/",
    }],
    ["noncommercial license", {
      license_text: "CC BY-NC 4.0",
      license_code: "CC BY-NC 4.0",
      license_url: "https://creativecommons.org/licenses/by-nc/4.0/",
    }],
  ])("rejects %s", (_name, change) => {
    expect(validateAvailableCuratedPhoto(
      { ...publishedInaturalistPhoto, ...change },
      "Selasphorus rufus",
    )).toBeNull();
  });
});

describe("published Wikimedia Commons recommendation photo validation", () => {
  it("accepts the immutable copy tied to one exact Commons File page", () => {
    expect(validateAvailableCuratedPhoto(publishedWikimediaPhoto, "Melozone aberti")).toMatchObject({
      providerLabel: "Wikimedia Commons",
      sourceUrl: publishedWikimediaPhoto.source_url,
      displayUrl: publishedWikimediaPhoto.display_url,
      licenseCode: "CC BY 2.5",
    });
  });

  it.each([
    ["live Commons image", { display_url: "https://upload.wikimedia.org/wikipedia/commons/a/ab/Bird.jpg" }],
    ["malformed source record", { source_record_id: "wikimedia-123" }],
    ["category source", { source_url: "https://commons.wikimedia.org/wiki/Category:Melozone_aberti" }],
    ["source fragment", { source_url: `${publishedWikimediaPhoto.source_url}#file` }],
    ["publisher claim", { publisher: "Wikimedia Foundation" }],
    ["oversized derivative", { original_width: 651 }],
    ["noncommercial license", {
      license_text: "CC BY-NC 4.0",
      license_code: "CC BY-NC 4.0",
      license_url: "https://creativecommons.org/licenses/by-nc/4.0/",
    }],
  ])("rejects %s", (_name, change) => {
    expect(validateAvailableCuratedPhoto(
      { ...publishedWikimediaPhoto, ...change },
      "Melozone aberti",
    )).toBeNull();
  });
});
