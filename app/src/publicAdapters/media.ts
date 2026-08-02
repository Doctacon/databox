import type { CatalogCall, CatalogPhoto, RecommendationCall, RecommendationPhoto } from "../types";

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

export function recommendationPhoto(scientificName: string | null): RecommendationPhoto {
  const { lookup_at: _lookupAt, ...photo } = unavailablePhoto(scientificName);
  return { ...photo, species_name: null };
}

export function recommendationCall(scientificName: string | null): RecommendationCall {
  const { lookup_at: _lookupAt, ...call } = unavailableCall(scientificName);
  return { ...call, species_name: null };
}
