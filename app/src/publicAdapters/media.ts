import type { CatalogCall, CatalogPhoto, RecommendationCall, RecommendationPhoto } from "../types";

const PUBLIC_MEDIA_URL = /^https:\/\/rufous-data\.loughondata\.com\/rufous-media\/v1\/objects\/([0-9a-f]{2})\/([0-9a-f]{64})\.webp$/;
const USFWS_SOURCE_URL = /^https:\/\/www\.fws\.gov\/media\/[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$/;
const INATURALIST_SOURCE_URL = /^https:\/\/www\.inaturalist\.org\/photos\/([1-9][0-9]*)$/;
const PUBLIC_DOMAIN_URL = "https://www.fws.gov/notices";
const USFWS_PHOTO_LICENSES = new Map([
  ["Public Domain", PUBLIC_DOMAIN_URL],
  ["CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"],
  ["CC BY 1.0", "https://creativecommons.org/licenses/by/1.0/"],
  ["CC BY 2.0", "https://creativecommons.org/licenses/by/2.0/"],
  ["CC BY 2.5", "https://creativecommons.org/licenses/by/2.5/"],
  ["CC BY 3.0", "https://creativecommons.org/licenses/by/3.0/"],
  ["CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"],
  ["CC BY-SA 1.0", "https://creativecommons.org/licenses/by-sa/1.0/"],
  ["CC BY-SA 2.0", "https://creativecommons.org/licenses/by-sa/2.0/"],
  ["CC BY-SA 2.5", "https://creativecommons.org/licenses/by-sa/2.5/"],
  ["CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/"],
  ["CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"],
]);
const INATURALIST_PHOTO_LICENSES = new Map([
  ["CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"],
  ["CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"],
  ["CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"],
]);
function plainText(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= maximum
    && value.trim() === value && !/[<>\u0000-\u001f\u007f]/.test(value);
}

function nullablePlainText(value: unknown, maximum: number): value is string | null {
  return value === null || plainText(value, maximum);
}

/** Fail-closed conversion from the published media contract into existing catalog UI data. */
export function publicCatalogPhoto(
  value: unknown,
  scientificName: string | null,
  generatedAt: string,
): CatalogPhoto | null {
  if (!value || typeof value !== "object" || Array.isArray(value) || scientificName === null) return null;
  const media = value as Record<string, unknown>;
  const imageMatch = typeof media.url === "string" ? PUBLIC_MEDIA_URL.exec(media.url) : null;
  const provider = media.provider === "usfws" || media.provider === "inaturalist"
    ? media.provider
    : null;
  const inaturalistSource = typeof media.source_url === "string"
    ? INATURALIST_SOURCE_URL.exec(media.source_url)
    : null;
  const inaturalistPhotoId = inaturalistSource?.[1] ?? null;
  const providerContractValid = provider === "usfws"
    ? typeof media.source_url === "string"
      && USFWS_SOURCE_URL.test(media.source_url)
      && typeof media.license === "string"
      && USFWS_PHOTO_LICENSES.get(media.license) === media.license_url
    : provider === "inaturalist"
      && inaturalistPhotoId !== null
      && media.media_id === `inaturalist-${inaturalistPhotoId}`
      && media.attribution_id === `inaturalist-attribution-${inaturalistPhotoId}`
      && typeof media.license === "string"
      && INATURALIST_PHOTO_LICENSES.get(media.license) === media.license_url;
  if (
    media.kind !== "photo" || !providerContractValid
    || !plainText(media.media_id, 256) || !plainText(media.attribution_id, 256)
    || media.scientific_name !== scientificName
    || !imageMatch || media.sha256 !== imageMatch[2] || imageMatch[1] !== imageMatch[2].slice(0, 2)
    || media.mime_type !== "image/webp"
    || !plainText(media.creator, 500) || !plainText(media.title, 500)
    || !nullablePlainText(media.caption, 2_000) || !plainText(media.alt_text, 1_000)
    || !Number.isSafeInteger(media.width) || Number(media.width) < 1 || Number(media.width) > 650
    || !Number.isSafeInteger(media.height) || Number(media.height) < 1 || Number(media.height) > 650
  ) return null;
  const isUsfws = provider === "usfws";
  return {
    status: "available",
    source_record_id: media.media_id,
    species_name: scientificName,
    display_url: media.url,
    source_url: media.source_url,
    creator: media.creator,
    rights_holder: null,
    publisher: isUsfws ? "U.S. Fish and Wildlife Service" : null,
    format: media.mime_type,
    license_text: media.license,
    license_url: media.license_url,
    selection_reason: isUsfws
      ? "Validated USFWS public-release photo"
      : "Validated iNaturalist public-release photo",
    provider,
    license_code: media.license,
    original_width: media.width,
    original_height: media.height,
    caveats: [],
    lookup_at: generatedAt,
    alt_text: media.alt_text,
    media_title: media.title,
    caption: media.caption,
    attribution_id: media.attribution_id,
  } as CatalogPhoto;
}

export function publicCatalogPhotos(
  value: unknown,
  scientificName: string | null,
  generatedAt: string,
): CatalogPhoto[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const photos: CatalogPhoto[] = [];
  for (const item of value) {
    const photo = publicCatalogPhoto(item, scientificName, generatedAt);
    const key = photo ? `${photo.source_record_id}|${photo.display_url}` : null;
    if (photo && key && !seen.has(key)) {
      seen.add(key);
      photos.push(photo);
    }
  }
  return photos;
}

export function unavailablePhoto(
  scientificName: string | null,
  lookupAt: string | null = null,
): CatalogPhoto {
  return {
    status: "unavailable",
    source_record_id: null,
    species_name: scientificName,
    display_url: null,
    source_url: null,
    creator: null,
    rights_holder: null,
    publisher: null,
    format: null,
    license_text: null,
    license_url: null,
    selection_reason: null,
    provider: null,
    license_code: null,
    original_width: null,
    original_height: null,
    caveats: ["No redistributable photo is included in this published release."],
    lookup_at: lookupAt,
  };
}

export function unavailableCall(
  scientificName: string | null,
  lookupAt: string | null = null,
): CatalogCall {
  return {
    status: "unavailable",
    source_record_id: null,
    recording_id: null,
    species_name: scientificName,
    geographic_scope: null,
    recording_type: null,
    quality: null,
    recordist: null,
    locality: null,
    country: null,
    source_url: null,
    audio_url: null,
    license_text: null,
    license_url: null,
    selection_reason: null,
    caveats: ["No redistributable call recording is included in this published release."],
    lookup_at: lookupAt,
  };
}

export function recommendationPhoto(
  scientificName: string | null,
  catalogPhoto: CatalogPhoto | null = null,
): RecommendationPhoto {
  if (catalogPhoto?.status === "available" && catalogPhoto.species_name === scientificName) {
    return {
      status: catalogPhoto.status,
      source_record_id: catalogPhoto.source_record_id,
      species_name: catalogPhoto.species_name,
      display_url: catalogPhoto.display_url,
      source_url: catalogPhoto.source_url,
      creator: catalogPhoto.creator,
      rights_holder: catalogPhoto.rights_holder,
      publisher: catalogPhoto.publisher,
      format: catalogPhoto.format,
      license_text: catalogPhoto.license_text,
      license_url: catalogPhoto.license_url,
      selection_reason: catalogPhoto.selection_reason,
      provider: catalogPhoto.provider,
      license_code: catalogPhoto.license_code,
      original_width: catalogPhoto.original_width,
      original_height: catalogPhoto.original_height,
      caveats: [...catalogPhoto.caveats],
    };
  }
  const { lookup_at: _lookupAt, ...photo } = unavailablePhoto(scientificName);
  return { ...photo, species_name: null };
}

export function recommendationCall(scientificName: string | null): RecommendationCall {
  const { lookup_at: _lookupAt, ...call } = unavailableCall(scientificName);
  return { ...call, species_name: null };
}
