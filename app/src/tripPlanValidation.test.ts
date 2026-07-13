import { describe, expect, it } from "vitest";
import type { TripPlanDetail } from "./types";
import { validateLocationSearch, validatePlanDetail, validatePlanList } from "./tripPlanValidation";

const plan: TripPlanDetail = {
  plan: {
    trip_plan_id: "trip_fixture", requested_location: "Prescott", normalized_location_name: "Prescott, Arizona",
    latitude: 34.54, longitude: -112.47, region_code: "US-AZ", timezone: "America/Phoenix",
    window_start: "2026-07-10T06:00:00", window_end: "2026-07-10T07:30:00", duration_minutes: 90,
    skill_level: "beginner", constraints_text: null, plan_status: "complete", field_plan_text: "Listen first.",
    caveats: ["Conditions change."], created_at: "2026-07-09T12:00:00", updated_at: "2026-07-09T12:00:00",
  },
  recommendations: [{
    recommendation_id: "rec_fixture", species_code: "mexjay", common_name: "Mexican Jay",
    scientific_name: "Aphelocoma wollweberi", recommendation_group: "high_likelihood", rank_order: 1,
    confidence_label: "high", rationale_text: "Recent public evidence", caveats: [],
    photo: { status: "unavailable", source_record_id: null, species_name: null, display_url: null, source_url: null, creator: null, rights_holder: null, publisher: null, format: null, license_text: null, license_url: null, selection_reason: null, provider: null, license_code: null, original_width: null, original_height: null, caveats: [] },
    call: { status: "unavailable", source_record_id: null, recording_id: null, species_name: null, geographic_scope: null, recording_type: null, quality: null, recordist: null, locality: null, country: null, source_url: null, audio_url: null, license_text: null, license_url: null, selection_reason: null, caveats: [] },
  }],
  evidence: [{ evidence_id: "evidence_fixture", recommendation_id: "rec_fixture", source: "ebird", source_table: "recent_observation_evidence", source_record_id: "S1", evidence_type: "recent_observation", status: "available", retrieved_at: null, summary: { location_name: "Public park" }, payload: { observation_count: 2 }, caveats: [] }],
  weather: { evidence_id: "weather_fixture", recommendation_id: null, source: "open_meteo", source_table: null, source_record_id: null, evidence_type: "weather_elevation_context", status: "available", retrieved_at: "2026-07-09T12:00:00", summary: {}, payload: { elevation_m: 1642 }, caveats: [] },
  media: [{ evidence_id: "media_fixture", recommendation_id: "rec_fixture", source_record_id: "XC1", recording_id: "1", status: "available", species_name: "Aphelocoma wollweberi", recording_type: "call", quality: "A", recordist: "Fixture", license_text: "CC BY 4.0", license_url: "https://creativecommons.org/licenses/by/4.0/", source_url: "https://xeno-canto.org/1", audio_url: "https://xeno-canto.org/1/download", caveats: [] }],
  tool_traces: [{ tool_trace_id: "trace_fixture", step_order: 1, tool_name: "normalize_location", tool_status: "ok", started_at: "2026-07-09T12:00:00", completed_at: "2026-07-09T12:00:01", input: { location: "Prescott" }, output_summary: { status: "ok" }, caveats: [] }],
  calendar_invite: { status: "not_created", sequence: null, outbox_id: null, allowed_actions: ["send"], can_retry: false, updated_at: null, acceptance_notice: null },
};
plan.evidence.push(structuredClone(plan.weather!));
plan.evidence.push({
  evidence_id: "media_fixture", recommendation_id: "rec_fixture", source: "xeno_canto", source_table: null,
  source_record_id: "XC1", evidence_type: "media_context", status: "available", retrieved_at: null,
  summary: { recording_id: "1" }, payload: {}, caveats: [],
});
function summary() {
  const { trip_plan_id, requested_location, normalized_location_name, window_start, window_end, duration_minutes, plan_status, caveats, created_at, updated_at } = plan.plan;
  return { trip_plan_id, requested_location, normalized_location_name, window_start, window_end, duration_minutes, plan_status, caveats, created_at, updated_at };
}

const suggestion = {
  display_name: "Prescott, Arizona", latitude: 34.54, longitude: -112.47,
  timezone: "America/Phoenix", region_code: "US-AZ", source: "open_meteo",
  source_id: "open_meteo_prescott", place_type: "Arizona place",
};

function inaturalistPlan(): TripPlanDetail {
  const value = structuredClone(plan);
  value.recommendations[0].photo = {
    status: "available", source_record_id: "42", species_name: "Aphelocoma wollweberi",
    display_url: "https://inaturalist-open-data.s3.amazonaws.com/photos/42/large.jpg",
    source_url: "https://www.inaturalist.org/photos/42", creator: "Fixture Photographer",
    rights_holder: null, publisher: null, format: null, license_text: "CC BY-SA 4.0",
    license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
    selection_reason: "First eligible photo in curated iNaturalist shortlist position 1",
    provider: "inaturalist", license_code: "CC BY-SA 4.0", original_width: 1600,
    original_height: 1200, caveats: [],
  };
  value.evidence.push({
    evidence_id: "photo_fixture", recommendation_id: "rec_fixture", source: "inaturalist",
    source_table: null, source_record_id: "42", evidence_type: "recommendation_photo",
    status: "available", retrieved_at: null, summary: {}, payload: {}, caveats: [],
  });
  return value;
}

describe("Trip Planner runtime response validation", () => {
  it("accepts exact bounded source-labeled location, summary, and nested detail contracts", () => {
    expect(validateLocationSearch({ locations: [suggestion] })).toHaveLength(1);
    expect(validatePlanList({ plans: [summary()] })).toEqual([summary()]);
    expect(validatePlanDetail(plan)).toEqual(plan);
    expect(validatePlanDetail(inaturalistPlan()).recommendations[0].photo.provider).toBe("inaturalist");
  });

  it.each([
    ["legacy provider", (value: TripPlanDetail) => { (value.recommendations[0].photo.provider as unknown) = "wikimedia_commons"; }],
    ["wrong display identity", (value: TripPlanDetail) => { value.recommendations[0].photo.display_url = value.recommendations[0].photo.display_url!.replace("/42/", "/41/"); }],
    ["original variant", (value: TripPlanDetail) => { value.recommendations[0].photo.display_url = value.recommendations[0].photo.display_url!.replace("/large.", "/original."); }],
    ["wrong source identity", (value: TripPlanDetail) => { value.recommendations[0].photo.source_url = "https://www.inaturalist.org/photos/41"; }],
    ["explicit port", (value: TripPlanDetail) => { value.recommendations[0].photo.source_url = "https://www.inaturalist.org:443/photos/42"; }],
    ["unsupported license", (value: TripPlanDetail) => { value.recommendations[0].photo.license_text = value.recommendations[0].photo.license_code = "CC BY-ND 4.0"; value.recommendations[0].photo.license_url = "https://creativecommons.org/licenses/by-nd/4.0/"; }],
    ["noncanonical license", (value: TripPlanDetail) => { value.recommendations[0].photo.license_url = "https://www.creativecommons.org/licenses/by-sa/4.0/"; }],
    ["extra photo field", (value: TripPlanDetail) => { (value.recommendations[0].photo as unknown as Record<string, unknown>).raw = "hidden"; }],
  ])("rejects unsafe planner iNaturalist %s before rendering", (_name, mutate) => {
    const value = inaturalistPlan();
    mutate(value);
    expect(() => validatePlanDetail(value)).toThrow("Invalid trip planner response");
  });

  it.each([
    ["extra root field", { ...plan, raw_model_response: "hidden" }],
    ["missing root field", Object.fromEntries(Object.entries(plan).filter(([key]) => key !== "media"))],
    ["wrong nested type", { ...plan, recommendations: [{ ...plan.recommendations[0], photo: [] }] }],
    ["oversized nested list", { ...plan, recommendations: Array.from({ length: 21 }, (_, index) => ({ ...plan.recommendations[0], recommendation_id: `rec_${index}`, rank_order: index + 1 })) }],
    ["nonfinite coordinate", { ...plan, plan: { ...plan.plan, latitude: Number.POSITIVE_INFINITY } }],
    ["unknown evidence recommendation", { ...plan, evidence: [{ ...plan.evidence[0], recommendation_id: "rec_unknown" }] }],
    ["unknown media recommendation", { ...plan, media: [{ ...plan.media[0], recommendation_id: "rec_unknown" }] }],
    ["raw-model payload key", { ...plan, evidence: [{ ...plan.evidence[0], payload: { raw_model_response: "hidden" } }] }],
    ["trace time reversal", { ...plan, tool_traces: [{ ...plan.tool_traces[0], started_at: "2026-07-09T12:00:02", completed_at: "2026-07-09T12:00:01" }] }],
    ["weather identity mismatch", { ...plan, weather: { ...plan.weather!, source: "untrusted" } }],
  ])("rejects %s before rendering", (_name, value) => {
    expect(() => validatePlanDetail(value)).toThrow("Invalid trip planner response");
  });

  it.each([
    ["unknown invite status", { ...plan.calendar_invite, status: "sent" }],
    ["action not allowed for status", { ...plan.calendar_invite, allowed_actions: ["send_update"] }],
    ["duplicate action", { ...plan.calendar_invite, allowed_actions: ["send", "send"] }],
    ["transport field", { ...plan.calendar_invite, recipient: "private@example.test" }],
    ["created state without identity", { ...plan.calendar_invite, status: "failed", allowed_actions: ["retry_failed"], can_retry: true }],
    ["accepted state without notice", { ...plan.calendar_invite, status: "accepted", sequence: 0, outbox_id: `trip_outbox_${"a".repeat(64)}`, allowed_actions: ["send_update"], updated_at: "2026-07-10T12:00:00Z" }],
  ])("rejects malformed calendar relationship: %s", (_name, calendar_invite) => {
    expect(() => validatePlanDetail({ ...plan, calendar_invite })).toThrow("Invalid trip planner response");
  });

  it("rejects duplicate summaries, malformed locations, and exact cardinality overflow", () => {
    expect(() => validatePlanList({ plans: [summary(), summary()] })).toThrow("Invalid trip planner response");
    expect(validatePlanList({ plans: Array.from({ length: 100 }, (_, index) => ({ ...summary(), trip_plan_id: `trip_${index}` })) })).toHaveLength(100);
    expect(() => validatePlanList({ plans: Array.from({ length: 101 }, (_, index) => ({ ...summary(), trip_plan_id: `trip_${index}` })) })).toThrow("Invalid trip planner response");
    expect(() => validateLocationSearch({ locations: [{ ...suggestion, latitude: Number.NaN }] })).toThrow("Invalid trip planner response");
    expect(() => validateLocationSearch({ locations: Array.from({ length: 6 }, (_, index) => ({ ...suggestion, source_id: `place_${index}` })) })).toThrow("Invalid trip planner response");
    expect(() => validateLocationSearch({ locations: [{ ...suggestion, place_type: "Birding hotspot" }] })).toThrow("Invalid trip planner response");
    expect(() => validateLocationSearch({ locations: [{ ...suggestion, source_id: "wrong_source" }] })).toThrow("Invalid trip planner response");
    expect(() => validateLocationSearch({ locations: [{ ...suggestion, private_note: "hidden" }] })).toThrow("Invalid trip planner response");
    expect(() => validateLocationSearch({ locations: [suggestion, { ...suggestion, source_id: "other", latitude: 34.5405 }] })).toThrow("Invalid trip planner response");
  });

  it.each([
    "2026-02-29T06:00:00",
    "2024-02-30T06:00:00",
    "2026-04-31T06:00:00",
    "2026-01-01T24:00:00",
    "2026-01-01T06:60:00",
    "2026-01-01T06:00:60",
    "2026-01-01T06:00:00+24:00",
    "0000-01-01T06:00:00",
  ])("rejects impossible ISO timestamp %s", (invalidTimestamp) => {
    const value = structuredClone(plan);
    value.plan.window_start = invalidTimestamp;
    expect(() => validatePlanDetail(value)).toThrow("Invalid trip planner response");
  });

  it("accepts leap days, microseconds, offsets, and exact duration relationships", () => {
    const value = structuredClone(plan);
    value.plan.window_start = "2024-02-29T06:00:00.123456+00:00";
    value.plan.window_end = "2024-02-29T07:30:00.123456Z";
    expect(validatePlanDetail(value).plan.window_start).toBe(value.plan.window_start);
  });

  it("enforces exact weather and derived media evidence identity", () => {
    const weatherOrphan = structuredClone(plan);
    weatherOrphan.evidence = weatherOrphan.evidence.filter((item) => item.evidence_id !== weatherOrphan.weather!.evidence_id);
    expect(() => validatePlanDetail(weatherOrphan)).toThrow("Invalid trip planner response");

    const weatherMismatch = structuredClone(plan);
    weatherMismatch.weather!.caveats = ["changed"];
    expect(() => validatePlanDetail(weatherMismatch)).toThrow("Invalid trip planner response");

    const duplicateWeather = structuredClone(plan);
    duplicateWeather.evidence.push({ ...structuredClone(duplicateWeather.weather!), evidence_id: "weather_second" });
    expect(() => validatePlanDetail(duplicateWeather)).toThrow("Invalid trip planner response");

    for (const mutate of [
      (value: TripPlanDetail) => { value.media = []; },
      (value: TripPlanDetail) => { value.media[0].evidence_id = "evidence_orphan"; },
      (value: TripPlanDetail) => { value.media[0].recommendation_id = null; },
      (value: TripPlanDetail) => { value.media[0].source_record_id = "XC2"; },
      (value: TripPlanDetail) => { value.media[0].recording_id = "2"; },
      (value: TripPlanDetail) => { value.media.push({ ...value.media[0], evidence_id: "extra_media" }); },
    ]) {
      const value = structuredClone(plan);
      mutate(value);
      expect(() => validatePlanDetail(value)).toThrow("Invalid trip planner response");
    }
  });

  it("rejects duplicate/orphan recommendation enrichment and available nested media without evidence", () => {
    const photoEvidence = {
      evidence_id: "photo_fixture", recommendation_id: "rec_fixture", source: "curated_photo", source_table: null,
      source_record_id: "42", evidence_type: "recommendation_photo", status: "unavailable", retrieved_at: null,
      summary: {}, payload: {}, caveats: ["unavailable"],
    };
    const duplicate = structuredClone(plan);
    duplicate.evidence.push(photoEvidence, { ...photoEvidence, evidence_id: "photo_second" });
    expect(() => validatePlanDetail(duplicate)).toThrow("Invalid trip planner response");

    const orphan = structuredClone(plan);
    orphan.evidence.push({ ...photoEvidence, recommendation_id: null });
    expect(() => validatePlanDetail(orphan)).toThrow("Invalid trip planner response");

    const availablePhoto = structuredClone(plan);
    availablePhoto.recommendations[0].photo = {
      status: "available", source_record_id: "42", species_name: "Avis localis", display_url: "https://example.invalid/photo",
      source_url: "https://example.invalid/source", creator: "Creator", rights_holder: null, publisher: null, format: null,
      license_text: "CC BY 4.0", license_url: "https://creativecommons.org/licenses/by/4.0/", selection_reason: null,
      provider: "inaturalist", license_code: "CC BY 4.0", original_width: 1600, original_height: 1200, caveats: [],
    };
    expect(() => validatePlanDetail(availablePhoto)).toThrow("Invalid trip planner response");

    const availableCall = structuredClone(plan);
    availableCall.recommendations[0].call = {
      status: "available", source_record_id: "XC1", recording_id: "1", species_name: "Avis localis",
      geographic_scope: "Arizona", recording_type: "call", quality: "A", recordist: "Recorder", locality: null,
      country: null, source_url: "https://xeno-canto.org/1", audio_url: "https://xeno-canto.org/1/download",
      license_text: "CC BY 4.0", license_url: "https://creativecommons.org/licenses/by/4.0/", selection_reason: null, caveats: [],
    };
    expect(() => validatePlanDetail(availableCall)).toThrow("Invalid trip planner response");
  });

  it("allows a valid sparse plan with no recommendations, weather, evidence, or media", () => {
    const sparse = structuredClone(plan);
    sparse.recommendations = [];
    sparse.evidence = [];
    sparse.weather = null;
    sparse.media = [];
    sparse.tool_traces = [];
    expect(validatePlanDetail(sparse)).toEqual(sparse);
  });
});
