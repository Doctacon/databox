import type {
  PublicAttribution,
  PublicAudio,
  PublicAudioProvider,
  PublicAudioSource,
  PublicBounds,
  PublicCell,
  PublicManifest,
  PublicMediaProvider,
  PublicMediaSource,
  PublicPlace,
  PublicPlaceShard,
  PublicReleasePointer,
  PublicSpeciesProfile,
  PublicSpeciesSummary,
} from "./publicTypes";
import { publicCatalogCall, publicCatalogPhoto } from "./publicAdapters/media";
import { isPublicSpeciesCode } from "./publicSpeciesCode";
import arizonaBoundariesRaw from "./assets/arizona-boundaries.geojson?raw";

const APPROVED_REMOTE_DATA_ROOT = "https://rufous-data.loughondata.com/rufous-public";
const configuredValue = import.meta.env.VITE_RUFOUS_DATA_BASE_URL?.trim();
const configuredDataRoot = configuredValue === APPROVED_REMOTE_DATA_ROOT ? configuredValue : undefined;
const DATA_ROOT = configuredDataRoot || "/data";
const SAME_ORIGIN_DATA_ROOT = "/data";
const REMOTE_TIMEOUT_MS = 3_000;
const MAX_RELEASE_BYTES = 256 * 1024 * 1024;
let activeDataRoot = SAME_ORIGIN_DATA_ROOT;
let activeDataVersion: string | null = null;
let activeMediaSource: PublicMediaSource = "none";
let activeAudioSource: PublicAudioSource = "none";
let activeTraitSource: "none" | "synthetic" | "avonet" = "none";
let activeAudioAttribution = new Map<string, {
  call: PublicAudio;
  commonName: string | null;
  scientificName: string | null;
}>();
let fallbackManifestPromise: Promise<PublicManifest> | null = null;
const SAFE_DATA_PATH = /^\/?(?:data\/)?(?:releases\/[a-f0-9_-]+\/)?(?:manifest|attribution|catalog|species\/[a-z0-9_-]+|cells\/[a-z0-9_-]+|places\/[a-z0-9_]+)\.json$/i;
const BOUNDARY_TOLERANCE = 1e-9;
const EBIRD_EOD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e";
const RUFOUS_TAXON_KEY = 2476855;
const AVONET_DATASET_DOI = "10.6084/m9.figshare.16586228.v7";
const AVONET_DATASET_URL = "https://doi.org/10.6084/m9.figshare.16586228.v7";
const AVONET_SOURCE_FILE_ID = 34480856;
const AVONET_SOURCE_FILE_MD5 = "1445afdcfb6df784010c2ca034544bc8";
const AVONET_CREDIT = "Joseph Tobias. AVONET: morphological, ecological and geographical data for all birds, version 7. Figshare. https://doi.org/10.6084/m9.figshare.16586228.v7";
const AVONET_MODIFICATIONS = "Rufous selected exact scientific-name matches for birds in the licensed Arizona occurrence release, renamed fields for the public profile, and omitted AVONET geographical range fields.";
const MEDIA_PROVIDERS_BY_SOURCE: Record<PublicMediaSource, readonly PublicMediaProvider[]> = {
  none: [],
  usfws: ["usfws"],
  inaturalist: ["inaturalist"],
  wikimedia: ["wikimedia"],
  "usfws+inaturalist": ["usfws", "inaturalist"],
  "usfws+wikimedia": ["usfws", "wikimedia"],
  "inaturalist+wikimedia": ["inaturalist", "wikimedia"],
  "usfws+inaturalist+wikimedia": ["usfws", "inaturalist", "wikimedia"],
};
const MEDIA_SOURCES = Object.freeze(Object.keys(MEDIA_PROVIDERS_BY_SOURCE) as PublicMediaSource[]);
const NONEMPTY_MEDIA_SOURCES: ReadonlySet<PublicMediaSource> = new Set(
  MEDIA_SOURCES.filter((source) => source !== "none"),
);
const AUDIO_PROVIDER_ORDER = ["xeno_canto", "inaturalist", "wikimedia", "usfws"] as const;
const AUDIO_SOURCES = [
  "none",
  ...Array.from({ length: 15 }, (_, index) => AUDIO_PROVIDER_ORDER
    .filter((_, providerIndex) => Boolean((index + 1) & (1 << providerIndex)))
    .join("+")),
] as PublicAudioSource[];

export const ARIZONA_STATE_RING = (JSON.parse(arizonaBoundariesRaw) as {
  features: Array<{
    properties?: { kind?: string };
    geometry?: { type?: string; coordinates?: number[][][] };
  }>;
}).features.find((feature) => feature.properties?.kind === "state")?.geometry?.coordinates?.[0] ?? [];

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    signal,
    headers: { Accept: "application/json" },
    credentials: "omit",
  });
  if (!response.ok) throw new Error(`Public data is unavailable (${response.status}).`);
  return response.json() as Promise<T>;
}

async function fetchVerifiedJson<T>(
  path: string,
  expectedSha256: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, {
    signal,
    headers: { Accept: "application/json" },
    credentials: "omit",
  });
  if (!response.ok) throw new Error(`Public data is unavailable (${response.status}).`);
  const bytes = await response.arrayBuffer();
  if (!crypto.subtle) throw new Error("This browser cannot verify the public release.");
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const actual = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  if (actual !== expectedSha256) throw new Error("The immutable Rufous manifest failed integrity verification.");
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)) as T;
  } catch {
    throw new Error("The immutable Rufous manifest is not valid UTF-8 JSON.");
  }
}

function joinPath(base: string, relative: string): string {
  return `${base.replace(/\/+$/, "")}/${relative.replace(/^\/+/, "")}`;
}

function rootPath(relative: string): string {
  return joinPath(activeDataRoot, relative);
}

function timedSignal(caller?: AbortSignal): { signal: AbortSignal; cleanup: () => void } {
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort(caller?.reason);
  if (caller?.aborted) abortFromCaller();
  else caller?.addEventListener("abort", abortFromCaller, { once: true });
  const timer = window.setTimeout(() => controller.abort(new DOMException("Timed out", "TimeoutError")), REMOTE_TIMEOUT_MS);
  return {
    signal: controller.signal,
    cleanup: () => {
      window.clearTimeout(timer);
      caller?.removeEventListener("abort", abortFromCaller);
    },
  };
}

function objectKeyUrl(base: string, key: string): string {
  if (/^https:\/\//i.test(base)) {
    const configured = new URL(base);
    return new URL(`/${key.replace(/^\/+/, "")}`, configured.origin).href;
  }
  return `/${key.replace(/^\/+/, "")}`;
}

function dataRelativePath(path: string, expectedDirectory: "species" | "cells" | "places" | "root"): string {
  if (path.includes("..") || !path.endsWith(".json") || !SAFE_DATA_PATH.test(path)) {
    throw new Error("The public data manifest contains an invalid shard path.");
  }
  const normalized = path.replace(/^\/+/, "").replace(/^data\//, "");
  const expected = expectedDirectory === "root" ? "" : `${expectedDirectory}/`;
  const releaseRelative = normalized.replace(/^releases\/[a-f0-9_-]+\//i, "");
  if (!releaseRelative.startsWith(expected)) {
    throw new Error("The public data manifest contains an invalid shard path.");
  }
  return releaseRelative;
}

function safePath(path: string, expectedDirectory: "species" | "cells" | "places" | "root"): string {
  const releaseRelative = dataRelativePath(path, expectedDirectory);
  if (/^https:\/\//i.test(activeDataRoot)) {
    return rootPath(releaseRelative);
  }
  if (activeDataRoot !== DATA_ROOT) return rootPath(releaseRelative);
  return path.startsWith("/") ? path : rootPath(releaseRelative);
}

function normalizedSearchKey(value: string): string {
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase().replace(/[^a-z0-9]/g, "");
}

export function normalizedPrefix(value: string): string | null {
  const normalized = normalizedSearchKey(value);
  if (!normalized) return null;
  return normalized.length === 1 ? `${normalized}_` : normalized.slice(0, 2);
}

function mediaProviders(source: PublicMediaSource): ReadonlySet<PublicMediaProvider> {
  return new Set(MEDIA_PROVIDERS_BY_SOURCE[source]);
}

function recognizedMediaSource(value: unknown): PublicMediaSource | null {
  return typeof value === "string" && MEDIA_SOURCES.includes(value as PublicMediaSource)
    ? value as PublicMediaSource
    : null;
}

function recognizedAudioSource(value: unknown): PublicAudioSource | null {
  return typeof value === "string" && AUDIO_SOURCES.includes(value as PublicAudioSource)
    ? value as PublicAudioSource
    : null;
}

function audioProviders(source: PublicAudioSource): ReadonlySet<PublicAudioProvider> {
  return new Set(source === "none" ? [] : source.split("+") as PublicAudioProvider[]);
}

const PUBLIC_AUDIO_FIELDS: readonly (keyof PublicAudio)[] = [
  "provider", "provider_id", "source_url", "creator", "license", "license_url", "url", "sha256",
  "bytes", "mime_type", "duration_seconds", "recording_type", "modifications", "attribution_id",
];

function samePublicAudio(left: PublicAudio | null | undefined, right: PublicAudio | null | undefined): boolean {
  if (left == null || right == null) return left == null && right == null;
  return PUBLIC_AUDIO_FIELDS.every((field) => left[field] === right[field]);
}

function audioAttributionFor(manifest: PublicManifest): typeof activeAudioAttribution {
  return new Map(manifest.species.flatMap((species) => species.call == null ? [] : [[
    species.call.attribution_id,
    { call: species.call, commonName: species.common_name, scientificName: species.scientific_name },
  ]]));
}

function nullablePlainText(value: unknown, maxLength: number): boolean {
  return value === null || (typeof value === "string"
    && value.length > 0 && value.length <= maxLength
    && !/[\u0000-\u001f\u007f]/.test(value));
}

function exactObjectKeys(value: object, expected: readonly string[]): boolean {
  const keys = Object.keys(value);
  return keys.length === expected.length && keys.every((key) => expected.includes(key));
}

/** Validates optional compact metadata without rejecting manifests published before it existed. */
function validCompactSpeciesSummary(species: PublicSpeciesSummary): boolean {
  const category = species.taxonomic_category;
  if (category !== undefined && category !== "species" && category !== "hybrid") return false;

  const family = species.family;
  if (family !== undefined && (
    family === null || typeof family !== "object" || Array.isArray(family)
    || !exactObjectKeys(family, ["common_name", "scientific_name"])
    || !nullablePlainText(family.common_name, 200)
    || !nullablePlainText(family.scientific_name, 200)
  )) return false;

  if (species.order_name !== undefined && !nullablePlainText(species.order_name, 200)) return false;

  const traitSummary = species.trait_summary;
  if (traitSummary !== undefined && (
    traitSummary === null || typeof traitSummary !== "object" || Array.isArray(traitSummary)
    || !exactObjectKeys(traitSummary, ["status", "mass_g", "habitat"])
    || (traitSummary.status !== "available" && traitSummary.status !== "unavailable")
    || (traitSummary.mass_g !== null && (typeof traitSummary.mass_g !== "number"
      || !Number.isFinite(traitSummary.mass_g) || traitSummary.mass_g <= 0 || traitSummary.mass_g > 1_000_000))
    || !nullablePlainText(traitSummary.habitat, 500)
  )) return false;

  const evidence = species.evidence;
  if (evidence !== undefined && (
    evidence === null || typeof evidence !== "object" || Array.isArray(evidence)
    || !exactObjectKeys(evidence, ["licensed_occurrence_count", "latest_licensed_occurrence_at"])
    || !Number.isSafeInteger(evidence.licensed_occurrence_count) || evidence.licensed_occurrence_count < 0
    || (evidence.latest_licensed_occurrence_at !== null
      && (typeof evidence.latest_licensed_occurrence_at !== "string"
        || !Number.isFinite(Date.parse(evidence.latest_licensed_occurrence_at))))
  )) return false;

  return true;
}

function profileMatchesCompactSummary(
  profile: PublicSpeciesProfile,
  species: PublicSpeciesSummary,
): boolean {
  if (species.taxonomic_category === undefined
    && species.family === undefined
    && species.order_name === undefined
    && species.trait_summary === undefined
    && species.evidence === undefined) return true;
  if (profile.traits === null || typeof profile.traits !== "object"
    || profile.family === null || typeof profile.family !== "object"
    || profile.evidence === null || typeof profile.evidence !== "object") return false;
  const traitsAvailable = Object.values(profile.traits).some((value) => value !== null);
  return (species.taxonomic_category === undefined
      || species.taxonomic_category === profile.taxonomic_category)
    && (species.family === undefined
      || (species.family.common_name === profile.family.common_name
        && species.family.scientific_name === profile.family.scientific_name))
    && (species.order_name === undefined || species.order_name === profile.order_name)
    && (species.trait_summary === undefined
      || (species.trait_summary.status === (traitsAvailable ? "available" : "unavailable")
        && species.trait_summary.mass_g === (typeof profile.traits.mass_g === "number"
          ? profile.traits.mass_g : null)
        && species.trait_summary.habitat === (typeof profile.traits.habitat === "string"
          ? profile.traits.habitat : null)))
    && (species.evidence === undefined
      || (species.evidence.licensed_occurrence_count === profile.evidence.licensed_occurrence_count
        && species.evidence.latest_licensed_occurrence_at
          === profile.evidence.latest_licensed_occurrence_at));
}

function validateManifest(manifest: PublicManifest): PublicManifest {
  const expectedOccurrenceSource = manifest.release_mode === "production" ? "gbif" : "synthetic";
  const expectedDatasetKey = manifest.release_mode === "production" ? EBIRD_EOD_DATASET_KEY : null;
  const expectedCoverage = manifest.release_mode === "production" ? "bounded_sample" : "fictional_fixture";
  const expectedRequiredTaxon = manifest.release_mode === "production" ? RUFOUS_TAXON_KEY : null;
  const mediaSource = recognizedMediaSource(manifest.source_policy?.media_source);
  const hasAudioPolicy = "audio_source" in (manifest.source_policy ?? {})
    || "audio_delivery" in (manifest.source_policy ?? {})
    || "audio_items" in (manifest.counts ?? {})
    || "species_with_audio" in (manifest.counts ?? {})
    || (Array.isArray(manifest.species) && manifest.species.some((species) => species.call != null));
  const audioSource = hasAudioPolicy
    ? recognizedAudioSource(manifest.source_policy?.audio_source)
    : "none";
  const validAudioPolicy = !hasAudioPolicy
    || (audioSource !== null
      && manifest.source_policy.audio_delivery === (audioSource === "none" ? "none" : "immutable_r2"));
  const validMediaPolicy = manifest.release_mode === "production"
    ? mediaSource !== null && NONEMPTY_MEDIA_SOURCES.has(mediaSource)
      && manifest.source_policy?.media_delivery === "immutable_r2"
    : (manifest.source_policy?.media_source === "none" && manifest.source_policy?.media_delivery === "none")
      || (mediaSource !== null && NONEMPTY_MEDIA_SOURCES.has(mediaSource)
        && manifest.source_policy?.media_delivery === "immutable_r2");
  const allowedMediaProviders: ReadonlySet<string> = mediaSource
    ? mediaProviders(mediaSource)
    : new Set<string>();
  const mediaItems = Array.isArray(manifest.species)
    ? manifest.species.reduce((total, species) => total + species.photo_count, 0)
    : -1;
  const speciesWithMedia = Array.isArray(manifest.species)
    ? manifest.species.filter((species) => species.photo_count > 0).length
    : -1;
  const allowedAudioProviders: ReadonlySet<string> = audioSource
    ? audioProviders(audioSource)
    : new Set<string>();
  const audioItems = Array.isArray(manifest.species)
    ? manifest.species.filter((species) => species.call != null).length
    : -1;
  const speciesWithAudio = audioItems;
  const audioCalls = Array.isArray(manifest.species)
    ? manifest.species.flatMap((species) => species.call == null ? [] : [species.call])
    : [];
  const hasTraitPolicy = "trait_source" in (manifest.source_policy ?? {})
    || "trait_delivery" in (manifest.source_policy ?? {})
    || "species_with_traits" in (manifest.counts ?? {})
    || (Array.isArray(manifest.species)
      && manifest.species.some((species) => species.trait_summary !== undefined));
  const compactFields = ["taxonomic_category", "family", "order_name", "trait_summary", "evidence"] as const;
  const hasCompactCatalogContract = Array.isArray(manifest.species)
    && manifest.species.some((species) => compactFields.some((field) => field in species));
  const validCompactCatalogContract = !hasCompactCatalogContract
    || manifest.species.every((species) => compactFields.every((field) => field in species));
  const expectedTraitSource = manifest.release_mode === "production" ? "avonet" : "synthetic";
  const speciesWithTraits = Array.isArray(manifest.species)
    ? manifest.species.filter((species) => species.trait_summary?.status === "available").length
    : -1;
  const validTraitPolicy = !hasTraitPolicy
    || (manifest.source_policy.trait_source === expectedTraitSource
      && manifest.source_policy.trait_delivery === "inline_static_json"
      && Number.isSafeInteger(manifest.counts.species_with_traits)
      && Number(manifest.counts.species_with_traits) === speciesWithTraits
      && (manifest.release_mode !== "production" || speciesWithTraits > 0));
  if (
    manifest.schema_version !== 1
    || manifest.mode !== "public"
    || !["synthetic", "production"].includes(manifest.release_mode)
    || manifest.region.code !== "US-AZ"
    || manifest.source_policy?.direct_ebird !== "excluded"
    || manifest.source_policy?.occurrence_source !== expectedOccurrenceSource
    || manifest.source_policy?.gbif_dataset_key !== expectedDatasetKey
    || manifest.source_policy?.coverage !== expectedCoverage
    || manifest.source_policy?.required_taxon_key !== expectedRequiredTaxon
    || !validMediaPolicy
    || !validAudioPolicy
    || !validTraitPolicy
    || !validCompactCatalogContract
    || manifest.license_policy?.version !== 1
    || !Number.isInteger(manifest.counts?.attribution_items)
    || !Number.isSafeInteger(manifest.counts?.media_items) || manifest.counts.media_items < 0
    || !Number.isSafeInteger(manifest.counts?.species_with_media) || manifest.counts.species_with_media < 0
    || (hasAudioPolicy && (!Number.isSafeInteger(manifest.counts?.audio_items) || Number(manifest.counts.audio_items) < 0))
    || (hasAudioPolicy && (!Number.isSafeInteger(manifest.counts?.species_with_audio) || Number(manifest.counts.species_with_audio) < 0))
    || !Array.isArray(manifest.species)
    || manifest.species.some((species) => !isPublicSpeciesCode(species.species_code)
      || !validCompactSpeciesSummary(species)
      || (manifest.release_mode === "production"
        && species.evidence?.latest_licensed_occurrence_at !== null
        && species.evidence?.latest_licensed_occurrence_at !== undefined
        && !/^\d{4}-\d{2}-\d{2}$/.test(species.evidence.latest_licensed_occurrence_at))
      || !Number.isSafeInteger(species.photo_count) || species.photo_count < 0
      || !("hero_photo" in species)
      || (species.photo_count === 0 && species.hero_photo !== null)
      || (species.photo_count > 0 && species.hero_photo === null)
      || (species.hero_photo !== null && !allowedMediaProviders.has(species.hero_photo.provider))
      || (species.call != null && (!allowedAudioProviders.has(species.call.provider)
        || publicCatalogCall(species.call, species.scientific_name, manifest.generated_at) === null)))
    || manifest.counts?.media_items !== mediaItems
    || manifest.counts?.species_with_media !== speciesWithMedia
    || (mediaSource === "none" && (mediaItems !== 0 || speciesWithMedia !== 0))
    || (mediaSource !== "none" && (mediaItems === 0 || speciesWithMedia === 0))
    || (hasAudioPolicy && manifest.counts?.audio_items !== audioItems)
    || (hasAudioPolicy && manifest.counts?.species_with_audio !== speciesWithAudio)
    || (audioSource === "none" && audioItems !== 0)
    || (audioSource !== null && audioSource !== "none" && audioItems === 0)
    || new Set(audioCalls.map((call) => call.attribution_id)).size !== audioItems
    || new Set(audioCalls.map((call) => `${call.provider}|${call.provider_id}`)).size !== audioItems
  ) {
    throw new Error("This Rufous public data release is not supported.");
  }
  return manifest;
}

function releasePointer(value: PublicManifest | PublicReleasePointer): PublicReleasePointer {
  const pointer = value as PublicReleasePointer;
  const sha256 = (item: unknown): item is string => typeof item === "string" && /^[0-9a-f]{64}$/.test(item);
  const safeKey = (key: unknown): key is string => typeof key === "string"
    && /^[a-z0-9._/-]{1,512}$/i.test(key) && !key.includes("..") && !key.startsWith("/");
  if (
    pointer.schema_version !== 1
    || pointer.mode !== "public-release-pointer"
    || !sha256(pointer.release_id)
    || !sha256(pointer.data_version)
    || !sha256(pointer.manifest_sha256)
    || !sha256(pointer.release_manifest_sha256)
    || typeof pointer.published_at !== "string" || !Number.isFinite(Date.parse(pointer.published_at))
    || !safeKey(pointer.manifest_path)
    || !safeKey(pointer.release_manifest_key)
    || !safeKey(pointer.asset_base_key)
    || !Number.isSafeInteger(pointer.file_count) || pointer.file_count < 0 || pointer.file_count > 20_000
    || !Number.isSafeInteger(pointer.total_bytes) || pointer.total_bytes < 0 || pointer.total_bytes > MAX_RELEASE_BYTES
    || !Array.isArray(pointer.previous_releases) || pointer.previous_releases.length > 100
  ) throw new Error("This Rufous public release pointer is not supported.");
  const assetBase = `rufous-public/releases/${pointer.release_id}/objects`;
  if (pointer.asset_base_key !== assetBase
    || pointer.manifest_path !== `${assetBase}/data/manifest.json`
    || pointer.release_manifest_key !== `rufous-public/releases/${pointer.release_id}/release.json`) {
    throw new Error("This Rufous public release pointer is not supported.");
  }
  return pointer;
}

async function resolveManifest(
  base: string,
  signal: AbortSignal | undefined,
  allowPointer: boolean,
): Promise<{ manifest: PublicManifest; dataRoot: string }> {
  const rootDocument = await fetchJson<PublicManifest | PublicReleasePointer>(joinPath(base, "manifest.json"), signal);
  if (rootDocument.mode === "public") {
    return { manifest: validateManifest(rootDocument), dataRoot: base };
  }
  if (!allowPointer) throw new Error("This Rufous public data release is not supported.");
  const pointer = releasePointer(rootDocument);
  const manifestUrl = objectKeyUrl(base, pointer.manifest_path);
  const manifest = validateManifest(await fetchVerifiedJson<PublicManifest>(manifestUrl, pointer.manifest_sha256, signal));
  if (manifest.data_version !== pointer.data_version) {
    throw new Error("The Rufous release pointer did not match its immutable manifest.");
  }
  return {
    manifest,
    dataRoot: manifestUrl.slice(0, -"/manifest.json".length),
  };
}

export async function getPublicManifest(signal?: AbortSignal): Promise<PublicManifest> {
  let resolution: { manifest: PublicManifest; dataRoot: string };
  if (configuredDataRoot) {
    const timed = timedSignal(signal);
    try {
      resolution = await resolveManifest(DATA_ROOT, timed.signal, true);
    } catch (configuredFailure) {
      if (signal?.aborted) throw configuredFailure;
      resolution = await resolveManifest(SAME_ORIGIN_DATA_ROOT, signal, false);
    } finally {
      timed.cleanup();
    }
  } else {
    resolution = await resolveManifest(SAME_ORIGIN_DATA_ROOT, signal, false);
  }
  // Swap only after the complete pointer + immutable manifest chain has passed validation.
  activeDataRoot = resolution.dataRoot;
  activeDataVersion = resolution.manifest.data_version;
  activeMediaSource = resolution.manifest.source_policy.media_source;
  activeAudioSource = resolution.manifest.source_policy.audio_source ?? "none";
  activeTraitSource = resolution.manifest.source_policy.trait_source ?? "none";
  activeAudioAttribution = audioAttributionFor(resolution.manifest);
  fallbackManifestPromise = null;
  return resolution.manifest;
}

async function sameReleasePagesManifest(signal?: AbortSignal): Promise<PublicManifest> {
  if (!activeDataVersion) throw new Error("The active Rufous release is unavailable.");
  if (!fallbackManifestPromise) {
    const expectedVersion = activeDataVersion;
    const pending = resolveManifest(SAME_ORIGIN_DATA_ROOT, signal, false).then((resolution) => {
      if (resolution.manifest.data_version !== expectedVersion) {
        throw new Error("The published data shard is unavailable and the bundled fallback is a different release.");
      }
      activeDataRoot = SAME_ORIGIN_DATA_ROOT;
      activeMediaSource = resolution.manifest.source_policy.media_source;
      activeAudioSource = resolution.manifest.source_policy.audio_source ?? "none";
      activeTraitSource = resolution.manifest.source_policy.trait_source ?? "none";
      activeAudioAttribution = audioAttributionFor(resolution.manifest);
      return resolution.manifest;
    }).catch((reason: unknown) => {
      if (fallbackManifestPromise === pending) fallbackManifestPromise = null;
      throw reason;
    });
    fallbackManifestPromise = pending;
  }
  return fallbackManifestPromise;
}

async function withCoherentShardFallback<T>(
  attempt: (requestSignal?: AbortSignal) => Promise<T>,
  fallback: (manifest: PublicManifest) => Promise<T>,
  signal?: AbortSignal,
): Promise<T> {
  const startedOnRemote = activeDataRoot.startsWith(`${APPROVED_REMOTE_DATA_ROOT}/releases/`);
  if (!startedOnRemote) return attempt(signal);

  const timed = timedSignal(signal);
  try {
    return await attempt(timed.signal);
  } catch (reason) {
    if (signal?.aborted) throw reason;
    const pagesManifest = await sameReleasePagesManifest(signal);
    return fallback(pagesManifest);
  } finally {
    timed.cleanup();
  }
}

export async function getPublicSpecies(
  species: PublicSpeciesSummary,
  signal?: AbortSignal,
): Promise<PublicSpeciesProfile> {
  if (!isPublicSpeciesCode(species.species_code)) throw new Error("Invalid species code.");
  const path = safePath(species.profile_path, "species");
  const load = async (url: string, requestSignal?: AbortSignal) => {
    const profile = await fetchJson<PublicSpeciesProfile>(url, requestSignal);
    if (profile.schema_version !== 1 || profile.species_code !== species.species_code
      || !profileMatchesCompactSummary(profile, species)
      || !Array.isArray(profile.media)
      || profile.media.some((item) => !mediaProviders(activeMediaSource).has(item.provider))
      || profile.media.some((item) => publicCatalogPhoto(item, profile.scientific_name, "") === null)
      || profile.media.length !== species.photo_count
      || (species.hero_photo === null
        ? profile.media.length !== 0
        : profile.media[0]?.media_id !== species.hero_photo.media_id)
      || (profile.call != null && (!audioProviders(activeAudioSource).has(profile.call.provider)
        || publicCatalogCall(profile.call, profile.scientific_name, "") === null))
      || !samePublicAudio(profile.call, species.call)) {
      throw new Error("The bird profile did not match the public catalog.");
    }
    return profile;
  };
  return withCoherentShardFallback(
    (requestSignal) => load(path, requestSignal),
    (manifest) => {
      const fallbackSpecies = manifest.species.find((item) => item.species_code === species.species_code);
      if (!fallbackSpecies) throw new Error("The bird profile is missing from the coherent bundled fallback.");
      return load(joinPath(SAME_ORIGIN_DATA_ROOT, dataRelativePath(fallbackSpecies.profile_path, "species")), signal);
    },
    signal,
  );
}

export async function getPublicCell(path: string, signal?: AbortSignal): Promise<PublicCell> {
  const relative = dataRelativePath(path, "cells");
  const primary = safePath(path, "cells");
  const expectedCellId = relative.slice("cells/".length, -".json".length);
  const load = async (url: string, requestSignal?: AbortSignal) => {
    const cell = await fetchJson<PublicCell>(url, requestSignal);
    if (cell.schema_version !== 1 || cell.cell_id !== expectedCellId || !Array.isArray(cell.observations)) {
      throw new Error("The observation shard did not match its manifest entry.");
    }
    return cell;
  };
  return withCoherentShardFallback(
    (requestSignal) => load(primary, requestSignal),
    (manifest) => {
      const fallbackCell = manifest.cells.find((item) => dataRelativePath(item.path, "cells") === relative);
      if (!fallbackCell) throw new Error("The observation shard is missing from the coherent bundled fallback.");
      return load(joinPath(SAME_ORIGIN_DATA_ROOT, dataRelativePath(fallbackCell.path, "cells")), signal);
    },
    signal,
  );
}

export async function getPublicAttribution(path: string, signal?: AbortSignal): Promise<PublicAttribution> {
  const primary = safePath(path, "root");
  const load = async (url: string, requestSignal?: AbortSignal) => {
    const attribution = await fetchJson<PublicAttribution>(url, requestSignal);
    const attributedProviders = Array.isArray(attribution.sources)
      ? new Set(attribution.sources.map((source) => source.provider))
      : new Set<string>();
    const audioItems = Array.isArray(attribution.items)
      ? attribution.items.filter((item) => item.kind === "audio")
      : [];
    const validAudioItems = audioItems.length === activeAudioAttribution.size
      && audioItems.every((item) => {
        const expected = activeAudioAttribution.get(item.attribution_id);
        return expected !== undefined
          && item.provider === expected.call.provider
          && item.provider_id === expected.call.provider_id
          && item.source_url === expected.call.source_url
          && item.creator === expected.call.creator
          && item.license === expected.call.license
          && item.license_url === expected.call.license_url
          && item.common_name === expected.commonName
          && item.scientific_name === expected.scientificName
          && item.recording_type === expected.call.recording_type
          && item.modifications === expected.call.modifications;
      });
    const avonetSources = Array.isArray(attribution.sources)
      ? attribution.sources.filter((source) => source.provider === "avonet")
      : [];
    const validTraitSource = activeTraitSource !== "avonet"
      || (avonetSources.length === 1
        && avonetSources[0].url === AVONET_DATASET_URL
        && avonetSources[0].license === "CC BY 4.0"
        && avonetSources[0].license_url === "https://creativecommons.org/licenses/by/4.0/"
        && avonetSources[0].credit === AVONET_CREDIT
        && avonetSources[0].modifications === AVONET_MODIFICATIONS
        && avonetSources[0].dataset_doi === AVONET_DATASET_DOI
        && avonetSources[0].dataset_version === "v7"
        && avonetSources[0].source_file_id === AVONET_SOURCE_FILE_ID
        && avonetSources[0].source_file_md5 === AVONET_SOURCE_FILE_MD5);
    if (attribution.schema_version !== 1 || !Array.isArray(attribution.sources) || !Array.isArray(attribution.items)
      || [...mediaProviders(activeMediaSource)].some((provider) => !attributedProviders.has(provider))
      || [...audioProviders(activeAudioSource)].some((provider) => !attributedProviders.has(provider))
      || !validTraitSource
      || !validAudioItems) {
      throw new Error("The attribution shard did not match its manifest entry.");
    }
    return attribution;
  };
  return withCoherentShardFallback(
    (requestSignal) => load(primary, requestSignal),
    (manifest) => load(joinPath(
      SAME_ORIGIN_DATA_ROOT,
      dataRelativePath(manifest.attribution_path, "root"),
    ), signal),
    signal,
  );
}

export async function searchPublicPlaces(
  query: string,
  manifest: PublicManifest,
  signal?: AbortSignal,
): Promise<PublicPlace[]> {
  const prefix = normalizedPrefix(query);
  if (!prefix) return [];
  const shard = manifest.place_prefixes.find((item) => item.prefix === prefix);
  if (!shard) return [];
  const load = async (url: string, requestSignal?: AbortSignal) => {
    const data = await fetchJson<PublicPlaceShard>(url, requestSignal);
    if (data.schema_version !== 1 || data.prefix !== prefix) {
      throw new Error("The place search shard did not match its manifest entry.");
    }
    return data;
  };
  const data = await withCoherentShardFallback(
    (requestSignal) => load(safePath(shard.path, "places"), requestSignal),
    (fallbackManifest) => {
      const fallbackShard = fallbackManifest.place_prefixes.find((item) => item.prefix === prefix);
      if (!fallbackShard) throw new Error("The place shard is missing from the coherent bundled fallback.");
      return load(joinPath(SAME_ORIGIN_DATA_ROOT, dataRelativePath(fallbackShard.path, "places")), signal);
    },
    signal,
  );
  const needle = normalizedSearchKey(query);
  return data.places
    .filter((place) => normalizedSearchKey(place.name).includes(needle))
    .sort((left, right) => {
      const leftStarts = normalizedSearchKey(left.name).startsWith(needle) ? 0 : 1;
      const rightStarts = normalizedSearchKey(right.name).startsWith(needle) ? 0 : 1;
      return leftStarts - rightStarts || left.name.localeCompare(right.name);
    })
    .slice(0, 10);
}

export function containsCoordinate(bounds: PublicBounds, latitude: number, longitude: number): boolean {
  return latitude >= bounds.south && latitude <= bounds.north
    && longitude >= bounds.west && longitude <= bounds.east
    && pointInArizona(latitude, longitude);
}

export function pointInArizona(latitude: number, longitude: number): boolean {
  let inside = false;
  for (let index = 0; index < ARIZONA_STATE_RING.length - 1; index += 1) {
    const start = ARIZONA_STATE_RING[index];
    const end = ARIZONA_STATE_RING[index + 1];
    if (pointOnSegment(longitude, latitude, start, end)) return true;
    const [startLongitude, startLatitude] = start;
    const [endLongitude, endLatitude] = end;
    if ((startLatitude > latitude) === (endLatitude > latitude)) continue;
    const crossingLongitude = startLongitude
      + ((latitude - startLatitude) * (endLongitude - startLongitude) / (endLatitude - startLatitude));
    if (longitude < crossingLongitude) inside = !inside;
  }
  return inside;
}

function pointOnSegment(
  longitude: number,
  latitude: number,
  start: number[],
  end: number[],
): boolean {
  const [startLongitude, startLatitude] = start;
  const [endLongitude, endLatitude] = end;
  const cross = (longitude - startLongitude) * (endLatitude - startLatitude)
    - (latitude - startLatitude) * (endLongitude - startLongitude);
  return Math.abs(cross) <= BOUNDARY_TOLERANCE
    && longitude >= Math.min(startLongitude, endLongitude) - BOUNDARY_TOLERANCE
    && longitude <= Math.max(startLongitude, endLongitude) + BOUNDARY_TOLERANCE
    && latitude >= Math.min(startLatitude, endLatitude) - BOUNDARY_TOLERANCE
    && latitude <= Math.max(startLatitude, endLatitude) + BOUNDARY_TOLERANCE;
}

export function parseArizonaCoordinates(value: string, bounds: PublicBounds): { latitude: number; longitude: number } | null {
  const match = /^\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*$/.exec(value);
  if (!match) return null;
  const latitude = Number(match[1]);
  const longitude = Number(match[2]);
  return Number.isFinite(latitude) && Number.isFinite(longitude) && containsCoordinate(bounds, latitude, longitude)
    ? { latitude, longitude }
    : null;
}
