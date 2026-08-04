import type { PublicMediaProvider } from "./publicTypes";

const USFWS_SOURCE_URL = /^https:\/\/www\.fws\.gov\/media\/[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$/;
const INATURALIST_SOURCE_URL = /^https:\/\/www\.inaturalist\.org\/photos\/([1-9][0-9]*)$/;
const WIKIMEDIA_SOURCE_URL = /^https:\/\/commons\.wikimedia\.org\/wiki\/File:[^/?#\u0000-\u0020\u007f]+$/;

export const WIKIMEDIA_PUBLIC_DOMAIN_URL =
  "https://commons.wikimedia.org/wiki/Commons:Copyright_tags/General_public_domain";

const COMMON_COMMERCIAL_LICENSES = new Map([
  ["CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"],
  ...["by", "by-sa"].flatMap((slug) =>
    ["1.0", "2.0", "2.5", "3.0", "4.0"].map((version) => [
      `CC ${slug.toUpperCase()} ${version}`,
      `https://creativecommons.org/licenses/${slug}/${version}/`,
    ] as const),
  ),
]);

const PUBLIC_MEDIA_LICENSES: Record<PublicMediaProvider, ReadonlyMap<string, string>> = {
  usfws: new Map([
    ["Public Domain", "https://www.fws.gov/notices"],
    ...COMMON_COMMERCIAL_LICENSES,
  ]),
  inaturalist: new Map([
    ["CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"],
    ["CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"],
    ["CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"],
  ]),
  wikimedia: new Map([
    ["Public Domain", WIKIMEDIA_PUBLIC_DOMAIN_URL],
    ...COMMON_COMMERCIAL_LICENSES,
  ]),
};

function canonicalWikimediaFilePage(value: string): boolean {
  if (value.length > 2_000 || !WIKIMEDIA_SOURCE_URL.test(value)) return false;
  try {
    const url = new URL(value);
    if (url.href !== value
      || url.protocol !== "https:"
      || url.host !== "commons.wikimedia.org"
      || url.username
      || url.password
      || url.port
      || url.search
      || url.hash) return false;
    const encodedName = url.pathname.slice("/wiki/File:".length);
    const name = decodeURIComponent(encodedName);
    return name.length > 0
      && name.length <= 500
      && name.trim() === name
      && name !== "."
      && name !== ".."
      && !/[\\/\u0000-\u001f\u007f]/.test(name);
  } catch {
    return false;
  }
}

export function isExactPublicMediaSourceUrl(
  provider: PublicMediaProvider,
  value: unknown,
): value is string {
  if (typeof value !== "string") return false;
  if (provider === "usfws") return USFWS_SOURCE_URL.test(value);
  if (provider === "inaturalist") return INATURALIST_SOURCE_URL.test(value);
  return canonicalWikimediaFilePage(value);
}

export function inaturalistPhotoId(value: unknown): string | null {
  if (typeof value !== "string") return null;
  return INATURALIST_SOURCE_URL.exec(value)?.[1] ?? null;
}

export function publicMediaLicenseUrl(
  provider: PublicMediaProvider,
  license: unknown,
): string | null {
  return typeof license === "string" ? PUBLIC_MEDIA_LICENSES[provider].get(license) ?? null : null;
}

export function publicMediaProviderLabel(
  provider: PublicMediaProvider,
): "USFWS" | "iNaturalist" | "Wikimedia Commons" {
  if (provider === "usfws") return "USFWS";
  if (provider === "inaturalist") return "iNaturalist";
  return "Wikimedia Commons";
}
