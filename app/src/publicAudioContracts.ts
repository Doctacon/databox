import type { PublicAudioProvider } from "./publicTypes";

const XENO_CANTO_SOURCE_URL = /^https:\/\/xeno-canto\.org\/([1-9][0-9]{0,9})$/;
const INATURALIST_SOURCE_URL = /^https:\/\/www\.inaturalist\.org\/observations\/([1-9][0-9]{0,19})$/;
const USFWS_SOURCE_URL = /^https:\/\/www\.fws\.gov\/media\/([a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?)$/;
const WIKIMEDIA_SOURCE_URL = /^https:\/\/commons\.wikimedia\.org\/wiki\/File:[^/?#\u0000-\u0020\u007f]+$/;

export const WIKIMEDIA_AUDIO_PUBLIC_DOMAIN_URL =
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

const PUBLIC_AUDIO_LICENSES: Record<PublicAudioProvider, ReadonlyMap<string, string>> = {
  xeno_canto: COMMON_COMMERCIAL_LICENSES,
  inaturalist: new Map([
    ["CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"],
    ["CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"],
    ["CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"],
  ]),
  wikimedia: new Map([
    ["Public Domain", WIKIMEDIA_AUDIO_PUBLIC_DOMAIN_URL],
    ...COMMON_COMMERCIAL_LICENSES,
  ]),
  usfws: new Map([
    ["Public Domain", "https://www.fws.gov/notices"],
    ...COMMON_COMMERCIAL_LICENSES,
  ]),
};

function wikimediaFileName(value: string): string | null {
  if (value.length > 2_000 || !WIKIMEDIA_SOURCE_URL.test(value)) return null;
  try {
    const url = new URL(value);
    if (url.href !== value
      || url.protocol !== "https:"
      || url.host !== "commons.wikimedia.org"
      || url.username
      || url.password
      || url.port
      || url.search
      || url.hash) return null;
    const name = decodeURIComponent(url.pathname.slice("/wiki/File:".length));
    return name.length > 0
      && name.length <= 500
      && name.trim() === name
      && name !== "."
      && name !== ".."
      && !/[\\/\u0000-\u001f\u007f]/.test(name)
      ? name
      : null;
  } catch {
    return null;
  }
}

export function isExactPublicAudioSourceUrl(
  provider: PublicAudioProvider,
  value: unknown,
): value is string {
  if (typeof value !== "string") return false;
  if (provider === "xeno_canto") return XENO_CANTO_SOURCE_URL.test(value);
  if (provider === "inaturalist") return INATURALIST_SOURCE_URL.test(value);
  if (provider === "usfws") return USFWS_SOURCE_URL.test(value);
  return wikimediaFileName(value) !== null;
}

export function publicAudioProviderIdMatchesSource(
  provider: PublicAudioProvider,
  providerId: unknown,
  sourceUrl: unknown,
): boolean {
  if (typeof providerId !== "string" || typeof sourceUrl !== "string") return false;
  if (provider === "xeno_canto") {
    const recordingId = XENO_CANTO_SOURCE_URL.exec(sourceUrl)?.[1];
    return recordingId !== undefined && providerId === `XC${recordingId}`;
  }
  if (provider === "inaturalist") {
    return INATURALIST_SOURCE_URL.test(sourceUrl) && /^sound-[1-9][0-9]{0,19}$/.test(providerId);
  }
  if (provider === "usfws") return providerId === USFWS_SOURCE_URL.exec(sourceUrl)?.[1];
  const fileName = wikimediaFileName(sourceUrl);
  return fileName !== null && providerId === `File:${fileName}`;
}

export function publicAudioLicenseUrl(
  provider: PublicAudioProvider,
  license: unknown,
): string | null {
  return typeof license === "string" ? PUBLIC_AUDIO_LICENSES[provider].get(license) ?? null : null;
}

export function publicAudioProviderLabel(
  provider: PublicAudioProvider,
): "Xeno-canto" | "iNaturalist" | "Wikimedia Commons" | "USFWS" {
  if (provider === "xeno_canto") return "Xeno-canto";
  if (provider === "inaturalist") return "iNaturalist";
  if (provider === "wikimedia") return "Wikimedia Commons";
  return "USFWS";
}

export function publicAudioProviderFromSourceUrl(value: unknown): PublicAudioProvider | null {
  for (const provider of ["xeno_canto", "inaturalist", "wikimedia", "usfws"] as const) {
    if (isExactPublicAudioSourceUrl(provider, value)) return provider;
  }
  return null;
}
