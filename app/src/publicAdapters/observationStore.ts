import type { PublicObservation } from "../publicTypes";
import { publicObservations } from "./runtime";

export interface PublicObservationQuery {
  speciesCode?: string;
  center?: { latitude: number; longitude: number; radiusMiles: number };
}

export async function queryPublicObservations(query: PublicObservationQuery = {}): Promise<PublicObservation[]> {
  return publicObservations(query);
}
