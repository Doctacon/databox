import {
  isExactPublicMediaSourceUrl,
  publicMediaLicenseUrl,
  publicMediaProviderLabel,
} from "./publicMediaContracts";

export const curatedPhotoKeys = [
  "status", "source_record_id", "species_name", "display_url", "source_url", "creator",
  "rights_holder", "publisher", "format", "license_text", "license_url", "selection_reason",
  "provider", "license_code", "original_width", "original_height", "caveats",
] as const;

type PhotoRecord = Record<string, unknown>;

export interface ValidatedCuratedPhoto {
  displayUrl: string;
  sourceUrl: string;
  providerLabel: "iNaturalist" | "USFWS" | "Wikimedia Commons";
  licenseUrl: string;
  licenseCode: string;
}

const LICENSES = new Map([
  ["CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"],
  ...["by", "by-sa", "by-nc", "by-nc-sa"].flatMap((slug) =>
    ["1.0", "2.0", "2.5", "3.0", "4.0"].map((version) => [
      `CC ${slug.toUpperCase()} ${version}`,
      `https://creativecommons.org/licenses/${slug}/${version}/`,
    ] as const),
  ),
]);

function boundedPlainText(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= maximum
    && value.trim() === value && value.replace(/\s+/g, " ") === value
    && !/[<>\u0000-\u001f\u007f]/.test(value);
}

function boundedPublicText(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= maximum
    && value.trim() === value && !/[<>\u0000-\u001f\u007f]/.test(value);
}

function strictProviderUrl(value: unknown, host: string): URL | null {
  if (typeof value !== "string" || value.length > 2000 || !value.startsWith(`https://${host}/`)) return null;
  try {
    const parsed = new URL(value);
    return parsed.href === value && parsed.protocol === "https:" && parsed.host === host
      && !parsed.username && !parsed.password && !parsed.port && !parsed.search && !parsed.hash
      ? parsed : null;
  } catch { return null; }
}

function validInaturalist(row: PhotoRecord): ValidatedCuratedPhoto | null {
  const id = row.source_record_id;
  if (typeof id !== "string" || !/^[1-9]\d*$/.test(id)) return null;
  const display = strictProviderUrl(row.display_url, "inaturalist-open-data.s3.amazonaws.com");
  const source = strictProviderUrl(row.source_url, "www.inaturalist.org");
  if (!display || !source
    || !new RegExp(`^/photos/${id}/large\\.(?:jpg|jpeg|png|webp)$`, "i").test(display.pathname)
    || source.pathname !== `/photos/${id}`) return null;
  return {
    displayUrl: display.href, sourceUrl: source.href, providerLabel: "iNaturalist",
    licenseUrl: row.license_url as string, licenseCode: row.license_code as string,
  };
}

function validUsfws(row: PhotoRecord): ValidatedCuratedPhoto | null {
  const display = strictProviderUrl(row.display_url, "rufous-data.loughondata.com");
  const source = strictProviderUrl(row.source_url, "www.fws.gov");
  if (!display || !source) return null;
  const image = /^\/rufous-media\/v1\/objects\/([0-9a-f]{2})\/([0-9a-f]{64})\.webp$/.exec(display.pathname);
  if (!image || image[1] !== image[2].slice(0, 2)
    || !/^\/media\/[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$/.test(source.pathname)) return null;
  return {
    displayUrl: display.href,
    sourceUrl: source.href,
    providerLabel: "USFWS",
    licenseUrl: row.license_url as string,
    licenseCode: row.license_code as string,
  };
}

function validPublishedInaturalist(row: PhotoRecord): ValidatedCuratedPhoto | null {
  const display = strictProviderUrl(row.display_url, "rufous-data.loughondata.com");
  const source = strictProviderUrl(row.source_url, "www.inaturalist.org");
  if (!display || !source) return null;
  const image = /^\/rufous-media\/v1\/objects\/([0-9a-f]{2})\/([0-9a-f]{64})\.webp$/.exec(display.pathname);
  const sourceMatch = /^\/photos\/([1-9][0-9]*)$/.exec(source.pathname);
  if (!image || image[1] !== image[2].slice(0, 2) || !sourceMatch
    || row.source_record_id !== `inaturalist-${sourceMatch[1]}`) return null;
  return {
    displayUrl: display.href,
    sourceUrl: source.href,
    providerLabel: "iNaturalist",
    licenseUrl: row.license_url as string,
    licenseCode: row.license_code as string,
  };
}

function validPublishedWikimedia(row: PhotoRecord): ValidatedCuratedPhoto | null {
  const display = strictProviderUrl(row.display_url, "rufous-data.loughondata.com");
  if (!display || !isExactPublicMediaSourceUrl("wikimedia", row.source_url)) return null;
  const image = /^\/rufous-media\/v1\/objects\/([0-9a-f]{2})\/([0-9a-f]{64})\.webp$/.exec(display.pathname);
  if (!image || image[1] !== image[2].slice(0, 2)
    || typeof row.source_record_id !== "string"
    || !/^wikimedia-[0-9a-f]{24}$/.test(row.source_record_id)) return null;
  return {
    displayUrl: display.href,
    sourceUrl: row.source_url,
    providerLabel: publicMediaProviderLabel("wikimedia"),
    licenseUrl: row.license_url as string,
    licenseCode: row.license_code as string,
  };
}

export function validateAvailableCuratedPhoto(
  row: PhotoRecord,
  scientificName: string | null,
): ValidatedCuratedPhoto | null {
  if (row.status !== "available" || scientificName === null || row.species_name !== scientificName) return null;
  if (row.provider === "usfws") {
    if (!boundedPublicText(row.source_record_id, 256) || !boundedPublicText(row.creator, 500)
      || row.selection_reason !== "Validated USFWS public-release photo"
      || row.rights_holder !== null || row.publisher !== "U.S. Fish and Wildlife Service"
      || row.format !== "image/webp"
      || typeof row.license_code !== "string" || row.license_text !== row.license_code
      || publicMediaLicenseUrl("usfws", row.license_code) !== row.license_url
      || !Number.isSafeInteger(row.original_width) || !Number.isSafeInteger(row.original_height)
      || Number(row.original_width) < 1 || Number(row.original_width) > 650
      || Number(row.original_height) < 1 || Number(row.original_height) > 650) return null;
    return validUsfws(row);
  }
  if (row.provider === "inaturalist"
    && row.selection_reason === "Validated iNaturalist public-release photo") {
    if (!boundedPublicText(row.creator, 500)
      || row.rights_holder !== null || row.publisher !== null || row.format !== "image/webp"
      || typeof row.license_code !== "string" || row.license_text !== row.license_code
      || publicMediaLicenseUrl("inaturalist", row.license_code) !== row.license_url
      || !Number.isSafeInteger(row.original_width) || !Number.isSafeInteger(row.original_height)
      || Number(row.original_width) < 1 || Number(row.original_width) > 650
      || Number(row.original_height) < 1 || Number(row.original_height) > 650) return null;
    return validPublishedInaturalist(row);
  }
  if (row.provider === "wikimedia"
    && row.selection_reason === "Validated Wikimedia Commons public-release photo") {
    if (!boundedPublicText(row.creator, 500)
      || row.rights_holder !== null || row.publisher !== null || row.format !== "image/webp"
      || typeof row.license_code !== "string" || row.license_text !== row.license_code
      || publicMediaLicenseUrl("wikimedia", row.license_code) !== row.license_url
      || !Number.isSafeInteger(row.original_width) || !Number.isSafeInteger(row.original_height)
      || Number(row.original_width) < 1 || Number(row.original_width) > 650
      || Number(row.original_height) < 1 || Number(row.original_height) > 650) return null;
    return validPublishedWikimedia(row);
  }
  if (!boundedPlainText(row.creator, 500) || !boundedPlainText(row.selection_reason, 500)
    || row.rights_holder !== null || row.publisher !== null || row.format !== null
    || typeof row.license_code !== "string" || row.license_text !== row.license_code
    || LICENSES.get(row.license_code) !== row.license_url
    || !Number.isSafeInteger(row.original_width) || !Number.isSafeInteger(row.original_height)
    || Number(row.original_width) < 1 || Number(row.original_height) < 1
    || Math.max(Number(row.original_width), Number(row.original_height)) < 1000
    || Math.min(Number(row.original_width), Number(row.original_height)) < 750
    || row.provider !== "inaturalist") return null;
  return validInaturalist(row);
}
