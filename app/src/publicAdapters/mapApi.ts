import type { MapEncounter, MapPhoto, MapSnapshot } from "../types";
import { publicCatalogPhoto, publicCatalogPhotos, unavailablePhoto } from "./media";
import { queryPublicObservations } from "./observationStore";
import { publicManifest, publicProfile } from "./runtime";

function timestamp(value: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? `${value}T12:00:00Z`
    : new Date(value).toISOString();
}

export async function getMapSnapshot(): Promise<MapSnapshot> {
  const [manifest, observations] = await Promise.all([publicManifest(), queryPublicObservations()]);
  const codes = [...new Set(observations.map((item) => item.species_code))];
  const profiles = manifest.species.length <= 50
    ? await Promise.all(codes.map((code) => publicProfile(code)))
    : [];
  const profileByCode = new Map(profiles.map((profile) => [profile.species_code, profile]));
  const summaryByCode = new Map(manifest.species.map((species) => [species.species_code, species]));
  const encounters: MapEncounter[] = observations.map((observation) => {
    const profile = profileByCode.get(observation.species_code);
    const species = summaryByCode.get(observation.species_code);
    return {
      source_observation_id: observation.public_id,
      species_code: observation.species_code,
      common_name: profile?.common_name ?? species?.common_name ?? null,
      scientific_name: profile?.scientific_name ?? species?.scientific_name ?? null,
      family_common_name: profile?.family.common_name ?? species?.family?.common_name ?? null,
      family_scientific_name: profile?.family.scientific_name ?? species?.family?.scientific_name ?? null,
      observation_at: timestamp(observation.observed_at),
      observation_count: Math.max(1, observation.count ?? 1),
      notable: observation.is_notable,
      location_id: `public-${observation.public_id}`,
      location_name: observation.location.name,
      latitude: observation.location.latitude,
      longitude: observation.location.longitude,
      access_warning: false,
    };
  }).sort((left, right) => right.observation_at.localeCompare(left.observation_at));
  const photos: MapPhoto[] = codes.map((code) => {
    const profile = profileByCode.get(code);
    const species = summaryByCode.get(code);
    const scientificName = profile?.scientific_name ?? species?.scientific_name ?? null;
    const photo = publicCatalogPhoto(species?.hero_photo, scientificName, manifest.generated_at)
      ?? publicCatalogPhotos(profile?.media, scientificName, manifest.generated_at)[0]
      ?? unavailablePhoto(scientificName, manifest.generated_at);
    return { species_code: code, scientific_name: scientificName, photo };
  });
  return {
    snapshot_latest_observation_at: encounters[0]?.observation_at ?? null,
    source_freshness_at: observations.length ? manifest.generated_at : null,
    encounters,
    photos,
  };
}
