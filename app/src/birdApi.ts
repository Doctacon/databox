import { isIsoDate, isIsoTimestamp } from "./isoDateTime";
import type { BirdCatalogSummary, BirdProfile } from "./types";

type UnknownRecord = Record<string, unknown>;

const summaryKeys = [
  "species_code", "common_name", "scientific_name", "taxonomic_category", "taxonomic_order",
  "order_name", "family_common_name", "family_scientific_name", "traits_status",
  "recent_public_observation_count", "latest_public_observation_at",
] as const;

function objectWithKeys(value: unknown, keys: readonly string[]): UnknownRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("invalid object");
  const row = value as UnknownRecord;
  const actual = Object.keys(row).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw new Error("unexpected fields");
  }
  return row;
}

function nullableString(value: unknown, max = 1000): value is string | null {
  return value === null || (typeof value === "string" && value.length <= max);
}

function nullableNumber(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}

function count(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function timestamp(value: unknown): value is string | null {
  return isIsoTimestamp(value, true);
}

function summary(value: unknown): BirdCatalogSummary {
  const row = objectWithKeys(value, summaryKeys);
  if (
    typeof row.species_code !== "string" || !/^[A-Za-z0-9]{1,64}$/.test(row.species_code)
    || !nullableString(row.common_name, 200) || !nullableString(row.scientific_name, 200)
    || (row.taxonomic_category !== "species" && row.taxonomic_category !== "hybrid")
    || !nullableNumber(row.taxonomic_order)
    || row.taxonomic_order === null || !nullableString(row.order_name, 200)
    || !nullableString(row.family_common_name, 200) || !nullableString(row.family_scientific_name, 200)
    || (row.traits_status !== "available" && row.traits_status !== "unavailable")
    || !count(row.recent_public_observation_count) || !timestamp(row.latest_public_observation_at)
  ) throw new Error("invalid catalog summary");
  return row as unknown as BirdCatalogSummary;
}

function validateProfile(value: unknown): BirdProfile {
  const row = objectWithKeys(value, [
    ...summaryKeys, "region_code", "taxonomy", "traits", "arizona_activity", "gbif",
    "xeno_canto", "freshness",
  ]);
  summary(Object.fromEntries(summaryKeys.map((key) => [key, row[key]])));
  if (row.region_code !== "US-AZ") throw new Error("invalid region");

  const taxonomy = objectWithKeys(row.taxonomy, ["family_code", "report_as", "extinct", "extinct_year"]);
  if (!nullableString(taxonomy.family_code, 64) || !nullableString(taxonomy.report_as, 64)
    || (taxonomy.extinct !== null && typeof taxonomy.extinct !== "boolean")
    || (taxonomy.extinct_year !== null && !count(taxonomy.extinct_year))) throw new Error("invalid taxonomy");

  const traits = objectWithKeys(row.traits, [
    "status", "source_scientific_name", "avonet_family", "avonet_order_name", "avibase_id",
    "inference", "traits_inferred", "reference_species", "mass_source", "mass_reference_other",
    "sample", "morphology", "ecology", "provenance",
  ]);
  if ((traits.status !== "available" && traits.status !== "unavailable")
    || !nullableString(traits.source_scientific_name, 200) || !nullableString(traits.avonet_family, 200)
    || !nullableString(traits.avonet_order_name, 200) || !nullableString(traits.avibase_id, 64)
    || (traits.inference !== null && typeof traits.inference !== "boolean")
    || !nullableString(traits.traits_inferred) || !nullableString(traits.reference_species, 200)
    || !nullableString(traits.mass_source) || !nullableString(traits.mass_reference_other)) {
    throw new Error("invalid traits");
  }
  if (traits.status !== row.traits_status) throw new Error("inconsistent trait status");

  const sample = objectWithKeys(traits.sample, [
    "total_individuals", "female_individuals", "male_individuals", "unknown_sex_individuals", "complete_measures",
  ]);
  if (Object.values(sample).some((item) => item !== null && !count(item))) throw new Error("invalid trait sample");

  const morphology = objectWithKeys(traits.morphology, [
    "beak_length_culmen_mm", "beak_length_nares_mm", "beak_width_mm", "beak_depth_mm",
    "tarsus_length_mm", "wing_length_mm", "kipps_distance_mm", "secondary_length_mm",
    "hand_wing_index", "tail_length_mm", "mass_g",
  ]);
  if (Object.values(morphology).some((item) => !nullableNumber(item))) throw new Error("invalid morphology");

  const ecology = objectWithKeys(traits.ecology, [
    "habitat", "habitat_density_code", "habitat_density_label", "migration_code", "migration_label",
    "trophic_level", "trophic_niche", "primary_lifestyle",
  ]);
  if (!nullableString(ecology.habitat, 200) || !nullableNumber(ecology.habitat_density_code)
    || !nullableString(ecology.habitat_density_label, 200) || !nullableNumber(ecology.migration_code)
    || !nullableString(ecology.migration_label, 200) || !nullableString(ecology.trophic_level, 200)
    || !nullableString(ecology.trophic_niche, 200) || !nullableString(ecology.primary_lifestyle, 200)) {
    throw new Error("invalid ecology");
  }

  const provenance = objectWithKeys(traits.provenance, [
    "dataset_doi", "dataset_version", "dataset_license", "source_file_id", "source_file_md5", "loaded_at",
  ]);
  if (!nullableString(provenance.dataset_doi, 200) || !nullableString(provenance.dataset_version, 64)
    || !nullableString(provenance.dataset_license, 64)
    || (provenance.source_file_id !== null && !count(provenance.source_file_id))
    || (provenance.source_file_md5 !== null && (typeof provenance.source_file_md5 !== "string"
      || !/^[0-9a-f]{32}$/.test(provenance.source_file_md5))) || !timestamp(provenance.loaded_at)) {
    throw new Error("invalid provenance");
  }

  const activity = objectWithKeys(row.arizona_activity, [
    "recent_public_observation_count", "latest_public_observation_at", "public_location_count",
    "recent_public_notable_count", "top_public_locations",
  ]);
  if (!count(activity.recent_public_observation_count)
    || activity.recent_public_observation_count !== row.recent_public_observation_count
    || !timestamp(activity.latest_public_observation_at)
    || activity.latest_public_observation_at !== row.latest_public_observation_at
    || !count(activity.public_location_count) || !count(activity.recent_public_notable_count)
    || !Array.isArray(activity.top_public_locations) || activity.top_public_locations.length > 10) {
    throw new Error("invalid Arizona activity");
  }
  for (const value of activity.top_public_locations) {
    const location = objectWithKeys(value, [
      "location_id", "location_name", "latitude", "longitude", "observation_count",
      "latest_observation_at", "notable_count",
    ]);
    if (typeof location.location_id !== "string" || location.location_id.length > 128
      || !nullableString(location.location_name, 300) || !nullableNumber(location.latitude)
      || location.latitude === null || location.latitude < -90 || location.latitude > 90
      || !nullableNumber(location.longitude) || location.longitude === null
      || location.longitude < -180 || location.longitude > 180 || !count(location.observation_count)
      || !timestamp(location.latest_observation_at) || !count(location.notable_count)) {
      throw new Error("invalid public location");
    }
  }

  const gbif = objectWithKeys(row.gbif, ["occurrence_count", "latest_event_date"]);
  if (!count(gbif.occurrence_count) || !isIsoDate(gbif.latest_event_date, true)) throw new Error("invalid GBIF context");

  const xeno = objectWithKeys(row.xeno_canto, [
    "recording_count", "latest_recording_date", "representative_recording_id", "representative_recordist",
    "representative_recording_type", "representative_recording_quality", "representative_recording_license",
  ]);
  if (!count(xeno.recording_count) || !isIsoDate(xeno.latest_recording_date, true)
    || !nullableString(xeno.representative_recording_id, 64)
    || !nullableString(xeno.representative_recordist, 300)
    || !nullableString(xeno.representative_recording_type, 300)
    || !nullableString(xeno.representative_recording_quality, 64)
    || !nullableString(xeno.representative_recording_license, 500)) throw new Error("invalid Xeno-canto context");

  const freshness = objectWithKeys(row.freshness, [
    "species_list_loaded_at", "taxonomy_loaded_at", "ebird_observations_loaded_at", "gbif_loaded_at",
    "xeno_canto_loaded_at", "catalog_freshness_at",
  ]);
  if (Object.values(freshness).some((item) => !timestamp(item))) throw new Error("invalid freshness");
  return row as unknown as BirdProfile;
}

const safeErrors: Record<number, Record<string, string>> = {
  400: { invalid_request: "Invalid bird species code" },
  404: { not_found: "Bird not found in the Arizona catalog" },
  503: {
    database_busy: "The warehouse is refreshing; try again shortly",
    database_unavailable: "The local bird catalog is unavailable",
  },
};

function safeErrorMessage(status: number, value: unknown): string {
  try {
    const wrapper = objectWithKeys(value, ["error"]);
    const error = objectWithKeys(wrapper.error, ["code", "message"]);
    if (typeof error.code !== "string" || typeof error.message !== "string") {
      return "The local bird catalog is unavailable";
    }
    const expected = safeErrors[status]?.[error.code];
    return expected === error.message ? expected : "The local bird catalog is unavailable";
  } catch {
    return "The local bird catalog is unavailable";
  }
}

async function birdRequest(path: string): Promise<unknown> {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" } });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error("The local bird catalog is unavailable");
  }
  if (!response.ok) throw new Error(safeErrorMessage(response.status, body));
  return body;
}

export async function listBirds(): Promise<BirdCatalogSummary[]> {
  const body = objectWithKeys(await birdRequest("/api/birds"), ["birds"]);
  if (!Array.isArray(body.birds) || body.birds.length !== 706) throw new Error("Invalid bird catalog response");
  const birds = body.birds.map(summary);
  const speciesCodes = birds.map((bird) => bird.species_code);
  const speciesCount = birds.filter((bird) => bird.taxonomic_category === "species").length;
  const hybridCount = birds.filter((bird) => bird.taxonomic_category === "hybrid").length;
  if (new Set(speciesCodes).size !== birds.length || speciesCount !== 624 || hybridCount !== 82) {
    throw new Error("Invalid bird catalog response");
  }
  return birds;
}

export async function getBird(speciesCode: string): Promise<BirdProfile> {
  if (!/^[A-Za-z0-9]{1,64}$/.test(speciesCode)) throw new Error("Invalid bird species code");
  const profile = validateProfile(await birdRequest(`/api/birds/${encodeURIComponent(speciesCode)}`));
  if (profile.species_code !== speciesCode) throw new Error("Invalid bird profile response");
  return profile;
}
