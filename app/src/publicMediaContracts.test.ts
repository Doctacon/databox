import { describe, expect, it } from "vitest";
import {
  isExactPublicMediaSourceUrl,
  publicMediaLicenseUrl,
  publicMediaProviderLabel,
  WIKIMEDIA_PUBLIC_DOMAIN_URL,
} from "./publicMediaContracts";

describe("public media provider contracts", () => {
  it.each([
    ["https://commons.wikimedia.org/wiki/File:Abert%27s_Towhee.jpg", true],
    ["https://commons.wikimedia.org/wiki/File:Violet-crowned_hummingbird_(Leucolia_violiceps).jpg", true],
    ["https://commons.wikimedia.org/wiki/File:Abert%27s_Towhee.jpg?download=1", false],
    ["https://commons.wikimedia.org/wiki/File:Abert%27s_Towhee.jpg#metadata", false],
    ["https://commons.wikimedia.org/wiki/Category:Abert%27s_Towhee", false],
    ["https://commons.wikimedia.org/wiki/File:..", false],
    ["https://commons.wikimedia.org/wiki/File:folder%2Fbird.jpg", false],
    ["https://commons.wikimedia.org/wiki/File:folder%5Cbird.jpg", false],
    ["https://user@commons.wikimedia.org/wiki/File:bird.jpg", false],
    ["https://commons.wikimedia.org:443/wiki/File:bird.jpg", false],
    ["https://commons.wikimedia.org.evil.example/wiki/File:bird.jpg", false],
  ])("validates one exact Commons File page: %s", (value, expected) => {
    expect(isExactPublicMediaSourceUrl("wikimedia", value)).toBe(expected);
  });

  it("uses the reviewed commercial-use licenses and human-facing provider label", () => {
    expect(publicMediaProviderLabel("wikimedia")).toBe("Wikimedia Commons");
    expect(publicMediaLicenseUrl("wikimedia", "Public Domain")).toBe(WIKIMEDIA_PUBLIC_DOMAIN_URL);
    expect(publicMediaLicenseUrl("wikimedia", "CC BY 2.5"))
      .toBe("https://creativecommons.org/licenses/by/2.5/");
    expect(publicMediaLicenseUrl("wikimedia", "CC BY-SA 4.0"))
      .toBe("https://creativecommons.org/licenses/by-sa/4.0/");
    expect(publicMediaLicenseUrl("wikimedia", "CC BY-NC 4.0")).toBeNull();
  });
});
