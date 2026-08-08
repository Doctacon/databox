import { distanceMiles } from "../publicWatch";
import { isPublicSpeciesCode } from "../publicSpeciesCode";
import type { CreateTargetPlanInput, TargetCandidate, TargetPlan } from "../types";
import { fetchPublicWeather } from "../publicWeather";
import { queryPublicObservations } from "./observationStore";
import {
  localDateTimeIso,
  publicManifest,
  publicProfile,
  randomIdentifier,
  safeRead,
  safeWrite,
} from "./runtime";

const TARGET_PLANS_KEY = "rufous.public.target-plans.v1";
const MAX_TARGET_PLANS = 25;

function storedPlans(): TargetPlan[] {
  const rows = safeRead<unknown[]>(TARGET_PLANS_KEY, []);
  return Array.isArray(rows) ? rows.filter((row): row is TargetPlan => Boolean(
    row && typeof row === "object"
    && typeof (row as TargetPlan).target_plan_id === "string"
    && /^target_[0-9a-f]{32}$/.test((row as TargetPlan).target_plan_id),
  )).slice(0, MAX_TARGET_PLANS) : [];
}

function timestamp(value: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00Z` : new Date(value).toISOString();
}

export async function createTargetPlan(input: CreateTargetPlanInput): Promise<TargetPlan> {
  if (!isPublicSpeciesCode(input.species_code)
    || !Number.isFinite(input.radius_miles) || input.radius_miles < 1 || input.radius_miles > 300
    || !Number.isSafeInteger(input.duration_minutes) || input.duration_minutes < 1 || input.duration_minutes > 1_440) {
    throw new Error("Check the target-planning inputs and try again.");
  }
  const location = input.location_selection;
  const start = localDateTimeIso(input.start_at, location.timezone);
  const end = new Date(Date.parse(start) + input.duration_minutes * 60_000).toISOString();
  const [manifest, profile, observations, weatherSnapshot] = await Promise.all([
    publicManifest(),
    publicProfile(input.species_code),
    queryPublicObservations({
      speciesCode: input.species_code,
      center: {
        latitude: location.latitude,
        longitude: location.longitude,
        radiusMiles: input.radius_miles,
      },
    }),
    fetchPublicWeather({
      latitude: location.latitude,
      longitude: location.longitude,
      start,
      end,
    }).catch(() => null),
  ]);
  const grouped = new Map<string, typeof observations>();
  for (const observation of observations) {
    const miles = distanceMiles(
      location.latitude,
      location.longitude,
      observation.location.latitude,
      observation.location.longitude,
    );
    if (miles > input.radius_miles) continue;
    const key = `${observation.location.latitude.toFixed(5)}|${observation.location.longitude.toFixed(5)}|${observation.location.name}`;
    grouped.set(key, [...(grouped.get(key) ?? []), observation]);
  }
  const candidates: TargetCandidate[] = [...grouped.entries()].map(([key, rows]) => {
    const first = rows[0];
    const miles = distanceMiles(
      location.latitude,
      location.longitude,
      first.location.latitude,
      first.location.longitude,
    );
    return {
      location_id: `public-${key.replace(/[^a-z0-9]+/gi, "-").slice(0, 100)}`,
      location_name: first.location.name,
      latitude: first.location.latitude,
      longitude: first.location.longitude,
      observation_count: rows.length,
      latest_observation_at: rows.map((row) => timestamp(row.observed_at)).sort().at(-1)!,
      distance_km: miles * 1.609344,
      distance_miles: miles,
      evidence_loaded_at: manifest.generated_at,
    };
  }).sort((left, right) => left.distance_miles - right.distance_miles
    || right.latest_observation_at.localeCompare(left.latest_observation_at)).slice(0, 10);
  const hasCandidates = candidates.length > 0;
  const actionIds = hasCandidates
    ? ["try_top_location", "arrive_early", "verify_access", "review_freshness", "check_weather"]
    : ["arrive_early", "review_freshness", "check_weather"];
  const guidance = hasCandidates
    ? [
      `Start with ${candidates[0].location_name || "the nearest published location"}, about ${candidates[0].distance_miles.toFixed(1)} miles from your origin.`,
      "Arrive near the start of your selected window and spend the first several minutes listening quietly.",
      "Verify current public access, closures, and site rules before departure.",
      "Review the evidence dates before departure; historical occurrences do not guarantee current presence.",
      weatherSnapshot
        ? "Review the available saved NWS/USGS context, then verify current conditions again before leaving."
        : "Check a current National Weather Service forecast before leaving because live weather is not required by this static plan.",
    ]
    : [
      "Arrive near the start of your selected window and spend the first several minutes listening quietly.",
      "Review the snapshot date before departure; no licensed occurrence location qualified inside this radius.",
      weatherSnapshot
        ? "Review the available saved NWS/USGS context, then verify current conditions again before leaving."
        : "Check a current National Weather Service forecast before leaving because live weather is not required by this static plan.",
    ];
  const now = new Date().toISOString();
  const targetPlan: TargetPlan = {
    target_plan_id: randomIdentifier("target_"),
    species_code: input.species_code,
    common_name: profile.common_name,
    scientific_name: profile.scientific_name,
    taxonomic_category: profile.taxonomic_category === "hybrid" ? "hybrid" : "species",
    origin: {
      requested_location: input.location,
      normalized_location_name: location.display_name,
      latitude: location.latitude,
      longitude: location.longitude,
      timezone: location.timezone,
      region_code: "US-AZ",
    },
    radius_miles: input.radius_miles,
    radius_km: input.radius_miles * 1.609344,
    window_start: start,
    window_end: end,
    duration_minutes: input.duration_minutes,
    candidates,
    weather: weatherSnapshot ? {
      status: weatherSnapshot.status,
      retrieved_at: weatherSnapshot.retrieved_at,
      forecast_summary: { ...weatherSnapshot.forecast_summary },
      units: {
        temperature: "°C",
        relative_humidity: "%",
        precipitation_probability: "%",
        precipitation: "mm",
        wind_speed: "km/h",
        wind_gusts: "km/h",
        elevation: "m",
      },
      elevation_m: weatherSnapshot.elevation_m,
      caveats: [...weatherSnapshot.caveats],
    } : {
      status: "unavailable",
      retrieved_at: now,
      forecast_summary: {
        temperature_2m_min: null,
        temperature_2m_max: null,
        temperature_2m_avg: null,
        relative_humidity_2m_avg: null,
        precipitation_probability_max: null,
        precipitation_sum: null,
        wind_speed_10m_max: null,
        wind_gusts_10m_max: null,
        weather_codes: [],
        condition_summaries: [],
      },
      units: {
        temperature: "°C",
        relative_humidity: "%",
        precipitation_probability: "%",
        precipitation: "mm",
        wind_speed: "km/h",
        wind_gusts: "km/h",
        elevation: "m",
      },
      elevation_m: null,
      caveats: ["Live weather and elevation are optional and unavailable in this browser-generated plan."],
    },
    action_ids: actionIds,
    guidance,
    caveats: [
      "This deterministic browser plan uses generalized licensed historical occurrences.",
      "No AI model, email service, or private observation was used.",
      ...(hasCandidates ? [] : ["No qualifying licensed occurrence location exists inside the requested radius."]),
    ],
    evidence_freshness_at: candidates.map((candidate) => candidate.evidence_loaded_at)
      .filter((value): value is string => value !== null).sort().at(-1) ?? null,
    created_at: now,
  };
  safeWrite(TARGET_PLANS_KEY, [targetPlan, ...storedPlans()
    .filter((row) => row.target_plan_id !== targetPlan.target_plan_id)].slice(0, MAX_TARGET_PLANS));
  return targetPlan;
}

export async function getTargetPlan(id: string): Promise<TargetPlan> {
  if (!/^target_[0-9a-f]{32}$/.test(id)) throw new Error("Invalid target plan identifier.");
  const plan = storedPlans().find((row) => row.target_plan_id === id);
  if (!plan) throw new Error("That target plan is not saved in this browser.");
  return plan;
}
