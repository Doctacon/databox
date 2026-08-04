import type { CatalogCall, CatalogPhoto, RecommendationCall, RecommendationPhoto } from "../types";
import {
  inaturalistPhotoId,
  isExactPublicMediaSourceUrl,
  publicMediaLicenseUrl,
} from "../publicMediaContracts";
import {
  isExactPublicAudioSourceUrl,
  publicAudioLicenseUrl,
  publicAudioProviderIdMatchesSource,
  publicAudioProviderLabel,
} from "../publicAudioContracts";
import type { PublicAudioProvider, PublicMediaProvider } from "../publicTypes";

const PUBLIC_MEDIA_URL = /^https:\/\/rufous-data\.loughondata\.com\/rufous-media\/v1\/objects\/([0-9a-f]{2})\/([0-9a-f]{64})\.webp$/;
const PUBLIC_AUDIO_URL = /^https:\/\/rufous-data\.loughondata\.com\/rufous-audio\/v1\/objects\/([0-9a-f]{2})\/([0-9a-f]{64})\.(mp3|ogg|m4a|wav)$/;
const PUBLIC_AUDIO_MIME_BY_EXTENSION = new Map([
  ["mp3", "audio/mpeg"],
  ["ogg", "audio/ogg"],
  ["m4a", "audio/mp4"],
  ["wav", "audio/wav"],
]);
const PUBLIC_AUDIO_KEYS = new Set([
  "provider", "provider_id", "source_url", "creator", "license", "license_url", "url",
  "sha256", "bytes", "mime_type", "duration_seconds", "recording_type", "modifications", "attribution_id",
]);
const WIKIMEDIA_MEDIA_ID = /^wikimedia-[0-9a-f]{24}$/;
const WIKIMEDIA_ATTRIBUTION_ID = /^wikimedia-attribution-[0-9a-f]{24}$/;
function plainText(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= maximum
    && value.trim() === value && !/[<>\u0000-\u001f\u007f]/.test(value);
}

function nullablePlainText(value: unknown, maximum: number): value is string | null {
  return value === null || plainText(value, maximum);
}

function validProviderContract(
  media: Record<string, unknown>,
  provider: PublicMediaProvider | null,
): boolean {
  if (provider === null || typeof media.license !== "string"
    || publicMediaLicenseUrl(provider, media.license) !== media.license_url) return false;
  if (provider === "usfws") return isExactPublicMediaSourceUrl(provider, media.source_url);
  if (provider === "inaturalist") {
    const photoId = inaturalistPhotoId(media.source_url);
    return photoId !== null
      && media.media_id === `inaturalist-${photoId}`
      && media.attribution_id === `inaturalist-attribution-${photoId}`;
  }
  return isExactPublicMediaSourceUrl(provider, media.source_url)
    && typeof media.media_id === "string"
    && WIKIMEDIA_MEDIA_ID.test(media.media_id)
    && typeof media.attribution_id === "string"
    && WIKIMEDIA_ATTRIBUTION_ID.test(media.attribution_id);
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
  const provider: PublicMediaProvider | null = media.provider === "usfws"
    || media.provider === "inaturalist"
    || media.provider === "wikimedia"
    ? media.provider
    : null;
  const providerContractValid = validProviderContract(media, provider);
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
  return {
    status: "available",
    source_record_id: media.media_id,
    species_name: scientificName,
    display_url: media.url,
    source_url: media.source_url,
    creator: media.creator,
    rights_holder: null,
    publisher: provider === "usfws" ? "U.S. Fish and Wildlife Service" : null,
    format: media.mime_type,
    license_text: media.license,
    license_url: media.license_url,
    selection_reason: provider === "usfws"
      ? "Validated USFWS public-release photo"
      : provider === "inaturalist"
        ? "Validated iNaturalist public-release photo"
        : "Validated Wikimedia Commons public-release photo",
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

/** Fail-closed conversion from one pinned public-audio object into the existing player contract. */
export function publicCatalogCall(
  value: unknown,
  scientificName: string | null,
  generatedAt: string,
): CatalogCall | null {
  if (!value || typeof value !== "object" || Array.isArray(value) || scientificName === null) return null;
  const audio = value as Record<string, unknown>;
  const keys = Object.keys(audio);
  const provider: PublicAudioProvider | null = audio.provider === "xeno_canto"
    || audio.provider === "inaturalist"
    || audio.provider === "wikimedia"
    || audio.provider === "usfws"
    ? audio.provider
    : null;
  const objectMatch = typeof audio.url === "string" ? PUBLIC_AUDIO_URL.exec(audio.url) : null;
  if (
    keys.length !== PUBLIC_AUDIO_KEYS.size || keys.some((key) => !PUBLIC_AUDIO_KEYS.has(key))
    || provider === null
    || !plainText(audio.provider_id, 512)
    || !isExactPublicAudioSourceUrl(provider, audio.source_url)
    || !publicAudioProviderIdMatchesSource(provider, audio.provider_id, audio.source_url)
    || publicAudioLicenseUrl(provider, audio.license) !== audio.license_url
    || !objectMatch || audio.sha256 !== objectMatch[2] || objectMatch[1] !== objectMatch[2].slice(0, 2)
    || PUBLIC_AUDIO_MIME_BY_EXTENSION.get(objectMatch[3]) !== audio.mime_type
    || !Number.isSafeInteger(audio.bytes) || Number(audio.bytes) < 1 || Number(audio.bytes) > 25 * 1024 * 1024
    || typeof audio.duration_seconds !== "number" || !Number.isFinite(audio.duration_seconds)
    || audio.duration_seconds <= 0 || audio.duration_seconds > 3_600
    || !plainText(audio.creator, 500) || !plainText(audio.recording_type, 100)
    || !plainText(audio.modifications, 1_000)
    || audio.attribution_id !== `audio-attribution-${String(audio.sha256).slice(0, 24)}`
  ) return null;
  const providerLabel = publicAudioProviderLabel(provider);
  const recordingId = provider === "xeno_canto"
    ? String(audio.provider_id).slice(2)
    : String(audio.provider_id);
  return {
    status: "available",
    source_record_id: String(audio.provider_id),
    recording_id: recordingId,
    species_name: scientificName,
    geographic_scope: "Global example",
    recording_type: String(audio.recording_type),
    quality: null,
    recordist: String(audio.creator),
    locality: null,
    country: null,
    source_url: String(audio.source_url),
    audio_url: String(audio.url),
    license_text: String(audio.license),
    license_url: String(audio.license_url),
    selection_reason: `${providerLabel} · ${String(audio.modifications)}`,
    caveats: [],
    lookup_at: generatedAt,
  };
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
