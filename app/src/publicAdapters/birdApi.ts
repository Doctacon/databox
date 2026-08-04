import type { PublicSpeciesProfile, PublicSpeciesSummary } from "../publicTypes";
import { isPublicSpeciesCode } from "../publicSpeciesCode";
import type {
  BirdCatalogSummary,
  BirdProfile,
  BirdPublicLocation,
  BirdTraits,
} from "../types";
import {
  publicCatalogPhoto,
  publicCatalogPhotos,
  publicCatalogCall,
  unavailableCall,
  unavailablePhoto,
} from "./media";
import { publicManifest, publicObservations, publicProfile } from "./runtime";

function timestamp(value: string | null): string | null {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return `${value}T12:00:00Z`;
  return Number.isFinite(Date.parse(value)) ? new Date(value).toISOString() : null;
}

function traitText(profile: PublicSpeciesProfile, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = profile.traits[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return null;
}

function traitNumber(profile: PublicSpeciesProfile, ...keys: string[]): number | null {
  for (const key of keys) {
    const value = profile.traits[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function summary(
  species: PublicSpeciesSummary,
  profile: PublicSpeciesProfile | null,
  order: number,
  generatedAt: string,
): BirdCatalogSummary {
  const scientificName = profile?.scientific_name ?? species.scientific_name;
  const hasTraits = Boolean(profile && Object.values(profile.traits).some((value) => value !== null));
  const profileHero = publicCatalogPhotos(profile?.media, scientificName, generatedAt)[0] ?? null;
  const manifestHero = publicCatalogPhoto(species.hero_photo, scientificName, generatedAt);
  const publishedCall = publicCatalogCall(profile?.call ?? species.call, scientificName, generatedAt);
  return {
    species_code: species.species_code,
    common_name: profile?.common_name ?? species.common_name,
    scientific_name: scientificName,
    taxonomic_category: profile?.taxonomic_category === "hybrid" ? "hybrid" : "species",
    taxonomic_order: order,
    order_name: profile?.order_name ?? null,
    family_common_name: profile?.family.common_name ?? null,
    family_scientific_name: profile?.family.scientific_name ?? null,
    traits_status: hasTraits ? "available" : "unavailable",
    mass_g: profile ? traitNumber(profile, "mass_g", "body_mass_g") : null,
    habitat: profile ? traitText(profile, "habitat") : null,
    recent_public_observation_count: profile?.evidence.licensed_occurrence_count ?? 0,
    latest_public_observation_at: timestamp(profile?.evidence.latest_licensed_occurrence_at ?? null),
    photo: profileHero ?? manifestHero ?? unavailablePhoto(scientificName, generatedAt),
    call: publishedCall ?? unavailableCall(scientificName, generatedAt),
  };
}

function traits(profile: PublicSpeciesProfile, generatedAt: string): BirdTraits {
  const available = Object.values(profile.traits).some((value) => value !== null);
  return {
    status: available ? "available" : "unavailable",
    source_scientific_name: available ? profile.scientific_name : null,
    avonet_family: profile.family.scientific_name,
    avonet_order_name: profile.order_name,
    avibase_id: traitText(profile, "avibase_id"),
    inference: typeof profile.traits.inference === "boolean" ? profile.traits.inference : null,
    traits_inferred: traitText(profile, "traits_inferred"),
    reference_species: traitText(profile, "reference_species"),
    mass_source: traitText(profile, "mass_source"),
    mass_reference_other: traitText(profile, "mass_reference_other"),
    sample: {
      total_individuals: traitNumber(profile, "total_individuals"),
      female_individuals: traitNumber(profile, "female_individuals"),
      male_individuals: traitNumber(profile, "male_individuals"),
      unknown_sex_individuals: traitNumber(profile, "unknown_sex_individuals"),
      complete_measures: traitNumber(profile, "complete_measures"),
    },
    morphology: {
      beak_length_culmen_mm: traitNumber(profile, "beak_length_culmen_mm"),
      beak_length_nares_mm: traitNumber(profile, "beak_length_nares_mm"),
      beak_width_mm: traitNumber(profile, "beak_width_mm"),
      beak_depth_mm: traitNumber(profile, "beak_depth_mm"),
      tarsus_length_mm: traitNumber(profile, "tarsus_length_mm"),
      wing_length_mm: traitNumber(profile, "wing_length_mm"),
      kipps_distance_mm: traitNumber(profile, "kipps_distance_mm"),
      secondary_length_mm: traitNumber(profile, "secondary_length_mm"),
      hand_wing_index: traitNumber(profile, "hand_wing_index"),
      tail_length_mm: traitNumber(profile, "tail_length_mm"),
      mass_g: traitNumber(profile, "mass_g", "body_mass_g"),
    },
    ecology: {
      habitat: traitText(profile, "habitat"),
      habitat_density_code: traitNumber(profile, "habitat_density_code"),
      habitat_density_label: traitText(profile, "habitat_density_label"),
      migration_code: traitNumber(profile, "migration_code"),
      migration_label: traitText(profile, "migration_label", "migration"),
      trophic_level: traitText(profile, "trophic_level"),
      trophic_niche: traitText(profile, "trophic_niche"),
      primary_lifestyle: traitText(profile, "primary_lifestyle"),
    },
    provenance: {
      dataset_doi: traitText(profile, "dataset_doi"),
      dataset_version: traitText(profile, "dataset_version"),
      dataset_license: traitText(profile, "dataset_license"),
      source_file_id: traitNumber(profile, "source_file_id"),
      source_file_md5: traitText(profile, "source_file_md5"),
      loaded_at: available ? generatedAt : null,
    },
  };
}

export async function listBirds(): Promise<BirdCatalogSummary[]> {
  const manifest = await publicManifest();
  const profiles = manifest.species.length <= 50
    ? await Promise.all(manifest.species.map((item) => publicProfile(item.species_code)))
    : [];
  const byCode = new Map(profiles.map((profile) => [profile.species_code, profile]));
  return manifest.species.map((species, index) => summary(
    species,
    byCode.get(species.species_code) ?? null,
    index + 1,
    manifest.generated_at,
  ));
}

export async function getBird(speciesCode: string): Promise<BirdProfile> {
  if (!isPublicSpeciesCode(speciesCode)) throw new Error("Invalid bird species code.");
  const [manifest, profile, observations] = await Promise.all([
    publicManifest(),
    publicProfile(speciesCode),
    publicObservations({ speciesCode }),
  ]);
  const species = manifest.species.find((item) => item.species_code === speciesCode)!;
  const catalog = summary(species, profile, manifest.species.indexOf(species) + 1, manifest.generated_at);
  const profilePhotos = publicCatalogPhotos(profile.media, profile.scientific_name, manifest.generated_at);
  const photos = profilePhotos.length
    ? profilePhotos
    : catalog.photo.status === "available" ? [catalog.photo] : [];
  const locations = new Map<string, BirdPublicLocation>();
  for (const observation of observations) {
    const key = `${observation.location.latitude.toFixed(4)}:${observation.location.longitude.toFixed(4)}:${observation.location.name}`;
    const existing = locations.get(key);
    const observedAt = timestamp(observation.observed_at)!;
    if (existing) {
      existing.observation_count += 1;
      existing.notable_count += observation.is_notable ? 1 : 0;
      if (!existing.latest_observation_at || observedAt > existing.latest_observation_at) existing.latest_observation_at = observedAt;
    } else {
      locations.set(key, {
        location_id: `public-${observation.public_id}`,
        location_name: observation.location.name,
        latitude: observation.location.latitude,
        longitude: observation.location.longitude,
        observation_count: 1,
        latest_observation_at: observedAt,
        notable_count: observation.is_notable ? 1 : 0,
      });
    }
  }
  const topLocations = [...locations.values()]
    .sort((left, right) => right.observation_count - left.observation_count
      || (right.latest_observation_at ?? "").localeCompare(left.latest_observation_at ?? ""))
    .slice(0, 10);
  const latest = observations.map((item) => timestamp(item.observed_at)).filter((item): item is string => Boolean(item)).sort().at(-1)
    ?? catalog.latest_public_observation_at;
  const xenoCall = catalog.call.status === "available"
    && catalog.call.source_url?.startsWith("https://xeno-canto.org/")
    ? catalog.call
    : null;
  return {
    ...catalog,
    photo: photos[0] ?? catalog.photo,
    photos,
    recent_public_observation_count: observations.length || catalog.recent_public_observation_count,
    latest_public_observation_at: latest,
    region_code: "US-AZ",
    taxonomy: { family_code: null, report_as: null, extinct: null, extinct_year: null },
    traits: traits(profile, manifest.generated_at),
    arizona_activity: {
      recent_public_observation_count: observations.length || catalog.recent_public_observation_count,
      latest_public_observation_at: latest,
      public_location_count: locations.size,
      recent_public_notable_count: observations.filter((item) => item.is_notable).length,
      top_public_locations: topLocations,
    },
    gbif: {
      occurrence_count: manifest.source_policy.occurrence_source === "gbif" ? profile.evidence.licensed_occurrence_count : 0,
      latest_event_date: manifest.source_policy.occurrence_source === "gbif"
        ? profile.evidence.latest_licensed_occurrence_at?.slice(0, 10) ?? null
        : null,
    },
    xeno_canto: {
      recording_count: xenoCall ? 1 : 0,
      latest_recording_date: null,
      representative_recording_id: xenoCall?.recording_id ?? null,
      representative_recordist: xenoCall?.recordist ?? null,
      representative_recording_type: xenoCall?.recording_type ?? null,
      representative_recording_quality: xenoCall?.quality ?? null,
      representative_recording_license: xenoCall?.license_text ?? null,
    },
    freshness: {
      species_list_loaded_at: manifest.generated_at,
      taxonomy_loaded_at: manifest.generated_at,
      ebird_observations_loaded_at: null,
      gbif_loaded_at: manifest.source_policy.occurrence_source === "gbif" ? manifest.generated_at : null,
      xeno_canto_loaded_at: xenoCall ? manifest.generated_at : null,
      catalog_freshness_at: manifest.generated_at,
    },
  };
}
