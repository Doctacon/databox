import { parseArizonaCoordinates, searchPublicPlaces } from "../publicData";
import { distanceMiles } from "../publicWatch";
import type {
  CreatePlanInput,
  Evidence,
  LocationSuggestion,
  PlanSummary,
  Recommendation,
  ToolTrace,
  TripCalendarInviteStatus,
  TripPlanDetail,
} from "../types";
import { recommendationCall, recommendationPhoto } from "./media";
import { queryPublicObservations } from "./observationStore";
import {
  localDateTimeIso,
  publicManifest,
  randomIdentifier,
  safeRead,
  safeWrite,
} from "./runtime";

const PLANS_KEY = "rufous.public.trip-plans.v1";
const MAX_PLANS = 25;
const PLAN_RADIUS_MILES = 50;
const PLAN_RADIUS_KM = PLAN_RADIUS_MILES * 1.609344;

function plans(): TripPlanDetail[] {
  const rows = safeRead<unknown[]>(PLANS_KEY, []);
  return Array.isArray(rows) ? rows.filter((row): row is TripPlanDetail => Boolean(
    row && typeof row === "object"
    && typeof (row as TripPlanDetail).plan?.trip_plan_id === "string"
    && Array.isArray((row as TripPlanDetail).recommendations)
    && Array.isArray((row as TripPlanDetail).evidence),
  )).slice(0, MAX_PLANS) : [];
}

function planSummary(detail: TripPlanDetail): PlanSummary {
  const plan = detail.plan;
  return {
    trip_plan_id: plan.trip_plan_id,
    requested_location: plan.requested_location,
    normalized_location_name: plan.normalized_location_name,
    window_start: plan.window_start,
    window_end: plan.window_end,
    duration_minutes: plan.duration_minutes,
    plan_status: plan.plan_status,
    caveats: plan.caveats,
    created_at: plan.created_at,
    updated_at: plan.updated_at,
  };
}

function coordinateSuggestions(
  latitude: number,
  longitude: number,
): LocationSuggestion[] {
  const coordinate = `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
  return ([
    ["Arizona time", "America/Phoenix"],
    ["Mountain time", "America/Denver"],
  ] as const).map(([label, timezone]) => ({
    display_name: `${coordinate} · ${label}`,
    latitude,
    longitude,
    timezone,
    region_code: "US-AZ",
    source: "manual_coordinates",
    source_id: `coordinates-${latitude.toFixed(5).replace(".", "_")}-${Math.abs(longitude).toFixed(5).replace(".", "_")}-${timezone.endsWith("Phoenix") ? "az" : "mt"}`,
    place_type: "Arizona place",
  }));
}

export async function searchLocations(
  query: string,
  signal?: AbortSignal,
): Promise<LocationSuggestion[]> {
  const manifest = await publicManifest();
  const coordinates = parseArizonaCoordinates(query, manifest.region.bounds);
  if (coordinates) return coordinateSuggestions(coordinates.latitude, coordinates.longitude);
  const places = await searchPublicPlaces(query, manifest, signal);
  return places.flatMap((place): LocationSuggestion[] => {
    const base = {
      latitude: place.latitude,
      longitude: place.longitude,
      region_code: "US-AZ" as const,
      source: "usgs_gnis" as const,
      source_id: place.public_id,
      place_type: "Arizona place" as const,
    };
    if (place.timezone) return [{ ...base, display_name: place.name, timezone: place.timezone }];
    return ([
      ["Arizona time", "America/Phoenix"],
      ["Mountain time", "America/Denver"],
    ] as const).map(([label, timezone]) => ({ ...base, display_name: `${place.name} · ${label}`, timezone }));
  });
}

export async function listPlans(): Promise<PlanSummary[]> {
  return plans().map(planSummary).sort((left, right) => right.created_at.localeCompare(left.created_at));
}

export async function getPlan(id: string): Promise<TripPlanDetail> {
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(id)) throw new Error("Invalid trip plan identifier.");
  const detail = plans().find((row) => row.plan.trip_plan_id === id);
  if (!detail) throw new Error("That trip plan is not saved in this browser.");
  return detail;
}

function mapDistanceKm(
  centerLatitude: number,
  centerLongitude: number,
  latitude: number,
  longitude: number,
): number {
  const latitudeDelta = latitude - centerLatitude;
  const longitudeDelta = (longitude - centerLongitude) * Math.cos(centerLatitude * Math.PI / 180);
  return 111.32 * Math.sqrt(latitudeDelta ** 2 + longitudeDelta ** 2);
}

export async function createPlan(input: CreatePlanInput): Promise<TripPlanDetail> {
  const location = input.location_selection;
  if (!location) throw new Error("Choose an Arizona place or coordinate and its time zone from the suggestions.");
  if (!Number.isSafeInteger(input.duration_minutes) || input.duration_minutes < 1 || input.duration_minutes > 1_440) {
    throw new Error("Choose a valid trip duration.");
  }
  const start = localDateTimeIso(input.start_at, location.timezone);
  const end = new Date(Date.parse(start) + input.duration_minutes * 60_000).toISOString();
  const [manifest, observations] = await Promise.all([
    publicManifest(),
    queryPublicObservations({
      center: {
        latitude: location.latitude,
        longitude: location.longitude,
        radiusMiles: PLAN_RADIUS_MILES,
      },
    }),
  ]);
  const eligible = observations.map((observation) => ({
    observation,
    distanceMiles: distanceMiles(
      location.latitude,
      location.longitude,
      observation.location.latitude,
      observation.location.longitude,
    ),
    distanceKm: mapDistanceKm(
      location.latitude,
      location.longitude,
      observation.location.latitude,
      observation.location.longitude,
    ),
  })).filter((item) => item.distanceMiles <= PLAN_RADIUS_MILES && item.distanceKm <= PLAN_RADIUS_KM)
    .sort((left, right) => left.distanceMiles - right.distanceMiles
      || Date.parse(right.observation.observed_at) - Date.parse(left.observation.observed_at))
    .slice(0, 200);
  const bySpecies = new Map<string, typeof eligible>();
  for (const item of eligible) bySpecies.set(item.observation.species_code, [...(bySpecies.get(item.observation.species_code) ?? []), item]);
  const ranked = [...bySpecies.entries()].sort((left, right) => right[1].length - left[1].length
    || left[1][0].distanceMiles - right[1][0].distanceMiles).slice(0, 10);
  const speciesByCode = new Map(manifest.species.map((species) => [species.species_code, species]));
  const recommendations: Recommendation[] = ranked.map(([speciesCode, rows], index) => {
    const species = speciesByCode.get(speciesCode);
    return {
      recommendation_id: `recommendation_${index + 1}_${speciesCode}`,
      species_code: speciesCode,
      common_name: species?.common_name ?? null,
      scientific_name: species?.scientific_name ?? null,
      recommendation_group: "gbif_context",
      rank_order: index + 1,
      evidence_label: `${rows.length.toLocaleString()} licensed historical occurrence${rows.length === 1 ? "" : "s"}`,
      rationale_text: `${rows.length.toLocaleString()} licensed generalized occurrence${rows.length === 1 ? " is" : "s are"} available inside ${PLAN_RADIUS_MILES} miles; the nearest is ${rows[0].distanceMiles.toFixed(1)} miles away.`,
      caveats: ["Historical occurrence evidence does not guarantee current presence."],
      photo: recommendationPhoto(species?.scientific_name ?? null),
      call: recommendationCall(species?.scientific_name ?? null),
    };
  });
  const recommendationByCode = new Map(recommendations.map((row) => [row.species_code, row]));
  const evidence: Evidence[] = eligible.flatMap(({ observation, distanceKm }, index) => {
    const recommendation = recommendationByCode.get(observation.species_code);
    if (!recommendation) return [];
    return [{
      evidence_id: `evidence_${index + 1}_${observation.public_id}`,
      recommendation_id: recommendation.recommendation_id,
      source: "gbif",
      source_table: "published_sanitized_occurrences",
      source_record_id: observation.public_id,
      evidence_type: "occurrence_context",
      status: "available",
      retrieved_at: manifest.generated_at,
      summary: {
        common_name: recommendation.common_name,
        scientific_name: recommendation.scientific_name,
        locality: observation.location.name,
        distance_km: distanceKm,
      },
      payload: {
        latitude: observation.location.latitude,
        longitude: observation.location.longitude,
        distance_km: distanceKm,
        species_code: observation.species_code,
      },
      caveats: observation.source === "synthetic" ? ["Synthetic preview fixture."] : [],
    } satisfies Evidence];
  });
  const now = new Date().toISOString();
  const toolTraces: ToolTrace[] = [
    {
      tool_trace_id: "trace_recent_public_snapshot",
      step_order: 1,
      tool_name: "lookup_recent_observation_evidence",
      tool_status: "ok",
      started_at: now,
      completed_at: now,
      input: { region_code: "US-AZ" },
      output_summary: { enforced_radius_km: PLAN_RADIUS_KM, row_count: 0, source: "excluded" },
      caveats: ["Direct eBird evidence is excluded from the public release."],
    },
    {
      tool_trace_id: "trace_licensed_occurrences",
      step_order: 2,
      tool_name: "lookup_gbif_occurrence_evidence",
      tool_status: "ok",
      started_at: now,
      completed_at: now,
      input: { region_code: "US-AZ" },
      output_summary: { enforced_radius_km: PLAN_RADIUS_KM, row_count: evidence.length },
      caveats: [],
    },
    {
      tool_trace_id: "trace_deterministic_plan",
      step_order: 3,
      tool_name: "compose_deterministic_field_plan",
      tool_status: "ok",
      started_at: now,
      completed_at: now,
      input: { recommendation_count: recommendations.length },
      output_summary: { model_calls: 0 },
      caveats: [],
    },
  ];
  const tripPlanId = randomIdentifier("trip_");
  const names = recommendations.slice(0, 3).map((row) => row.common_name || row.scientific_name || row.species_code).filter(Boolean);
  const detail: TripPlanDetail = {
    plan: {
      trip_plan_id: tripPlanId,
      requested_location: input.location,
      normalized_location_name: location.display_name,
      latitude: location.latitude,
      longitude: location.longitude,
      region_code: "US-AZ",
      timezone: location.timezone,
      window_start: start,
      window_end: end,
      duration_minutes: input.duration_minutes,
      plan_status: "complete",
      skill_level: input.skill_level?.trim() || null,
      constraints_text: input.constraints?.trim() || null,
      field_plan_text: names.length
        ? `Begin quietly near ${location.display_name}. Prioritize ${names.join(", ")}; pause often to listen, keep to public access, and treat every historical occurrence as context rather than a promise of current presence.`
        : `Begin quietly near ${location.display_name}, pause often to listen, remain on public access, and use habitat cues because this release has no qualifying occurrence context inside ${PLAN_RADIUS_MILES} miles.`,
      caveats: [
        "This browser-generated plan uses generalized licensed historical occurrences.",
        "Live weather and AI prose are optional enhancements and were not used.",
        "Verify current access, conditions, and closures before visiting.",
      ],
      created_at: now,
      updated_at: now,
    },
    recommendations,
    evidence,
    weather: null,
    media: [],
    tool_traces: toolTraces,
    calendar_invite: {
      status: "not_created",
      sequence: null,
      outbox_id: null,
      allowed_actions: [],
      can_retry: false,
      updated_at: null,
      acceptance_notice: null,
    },
  };
  safeWrite(PLANS_KEY, [detail, ...plans().filter((row) => row.plan.trip_plan_id !== tripPlanId)].slice(0, MAX_PLANS));
  return detail;
}

export type TripCalendarAction = TripCalendarInviteStatus["allowed_actions"][number];

export async function actOnTripCalendarInvite(): Promise<TripCalendarInviteStatus> {
  throw new Error("Email delivery is not enabled in public Rufous. Download the calendar file instead.");
}
