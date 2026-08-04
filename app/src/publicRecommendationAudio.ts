import {
  publicAudioLicenseUrl,
  publicAudioProviderFromSourceUrl,
  publicAudioProviderIdMatchesSource,
  publicAudioProviderLabel,
} from "./publicAudioContracts";
import type { PublicAudioProvider } from "./publicTypes";
import type { RecommendationCall } from "./types";

const IMMUTABLE_PUBLIC_AUDIO_URL = /^https:\/\/rufous-data\.loughondata\.com\/rufous-audio\/v1\/objects\/([0-9a-f]{2})\/([0-9a-f]{64})\.(?:mp3|ogg|wav|m4a)$/;

export interface ValidatedPublicRecommendationAudio {
  provider: PublicAudioProvider;
  providerLabel: "Xeno-canto" | "iNaturalist" | "Wikimedia Commons" | "USFWS";
  providerId: string;
  recordingId: string;
  sourceUrl: string;
  audioUrl: string;
  licenseCode: string;
  licenseUrl: string;
}

/**
 * Revalidate the lossy RecommendationCall projection of one pinned public sound.
 *
 * The public catalog contract is stronger and also binds the URL to a SHA-256
 * field. RecommendationCall intentionally omits that operational field, so this
 * boundary still requires the exact content-addressed host, namespace, shard,
 * and digest grammar before a saved plan may render or play the sound.
 */
export function validatePublicRecommendationAudio(
  call: RecommendationCall,
): ValidatedPublicRecommendationAudio | null {
  if (
    call.status !== "available"
    || typeof call.source_record_id !== "string"
    || typeof call.recording_id !== "string"
    || typeof call.source_url !== "string"
    || typeof call.audio_url !== "string"
    || typeof call.license_text !== "string"
    || typeof call.license_url !== "string"
  ) return null;
  const provider = publicAudioProviderFromSourceUrl(call.source_url);
  if (provider === null || !publicAudioProviderIdMatchesSource(
    provider,
    call.source_record_id,
    call.source_url,
  )) return null;
  const expectedRecordingId = provider === "xeno_canto"
    ? call.source_record_id.slice(2)
    : call.source_record_id;
  if (call.recording_id !== expectedRecordingId) return null;
  const object = IMMUTABLE_PUBLIC_AUDIO_URL.exec(call.audio_url);
  if (object === null || object[1] !== object[2].slice(0, 2)) return null;
  const expectedLicenseUrl = publicAudioLicenseUrl(provider, call.license_text);
  if (expectedLicenseUrl === null || call.license_url !== expectedLicenseUrl) return null;
  return {
    provider,
    providerLabel: publicAudioProviderLabel(provider),
    providerId: call.source_record_id,
    recordingId: call.recording_id,
    sourceUrl: call.source_url,
    audioUrl: call.audio_url,
    licenseCode: call.license_text,
    licenseUrl: call.license_url,
  };
}

export function isImmutablePublicRecommendationAudioUrl(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const match = IMMUTABLE_PUBLIC_AUDIO_URL.exec(value);
  return match !== null && match[1] === match[2].slice(0, 2);
}
