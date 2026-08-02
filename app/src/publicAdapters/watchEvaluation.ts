import { distanceMiles } from "../publicWatch";
import { isPublicSpeciesCode } from "../publicSpeciesCode";
import type { BirdWatch } from "../types";
import { queryPublicObservations } from "./observationStore";

export interface BrowserWatchEvaluation {
  species_code: string;
  match_count: number;
  latest_observation_at: string | null;
  nearest_location_name: string | null;
  nearest_distance_miles: number | null;
}

export async function evaluateBrowserWatch(watch: BirdWatch): Promise<BrowserWatchEvaluation> {
  if (!isPublicSpeciesCode(watch.species_code)) throw new Error("Invalid bird species code.");
  const rows = (await queryPublicObservations({
    speciesCode: watch.species_code,
    center: {
      latitude: watch.center_latitude,
      longitude: watch.center_longitude,
      radiusMiles: watch.radius_miles,
    },
  })).map((observation) => ({
    observation,
    distance: distanceMiles(
      watch.center_latitude,
      watch.center_longitude,
      observation.location.latitude,
      observation.location.longitude,
    ),
  })).filter((item) => item.distance <= watch.radius_miles)
    .sort((left, right) => left.distance - right.distance);
  const latest = rows.map((item) => item.observation.observed_at).sort().at(-1) ?? null;
  return {
    species_code: watch.species_code,
    match_count: rows.length,
    latest_observation_at: latest,
    nearest_location_name: rows[0]?.observation.location.name ?? null,
    nearest_distance_miles: rows[0]?.distance ?? null,
  };
}
