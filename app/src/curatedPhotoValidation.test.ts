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
