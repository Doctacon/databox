import type { BirdProfile } from "./types";

// Synthetic public test data only; this is not a saved personal origin.
export const targetPlan = {
  target_plan_id: "target_0123456789abcdef0123456789abcdef",
  species_code: "target1", common_name: "Target Bird", scientific_name: "Avis target", taxonomic_category: "species",
  origin: { requested_location: "Synthetic Arizona Origin", normalized_location_name: "Synthetic Arizona Origin", latitude: 34, longitude: -112, timezone: "America/Phoenix", region_code: "US-AZ" },
  radius_miles: 25, radius_km: 40.234, window_start: "2026-07-11T06:00:00", window_end: "2026-07-11T08:00:00", duration_minutes: 120,
  candidates: [{ location_id: "L1", location_name: "Public Lake", latitude: 34.1, longitude: -112.1, observation_count: 2, latest_observation_at: "2026-07-10T07:00:00", distance_km: 14.323, distance_miles: 8.9, evidence_loaded_at: "2026-07-10T08:00:00" }],
  weather: { status: "available", retrieved_at: "2026-07-10T09:00:00Z", forecast_summary: { temperature_2m_min: 19, temperature_2m_max: 21, temperature_2m_avg: 20, relative_humidity_2m_avg: 39, precipitation_probability_max: 0, precipitation_sum: 0, wind_speed_10m_max: 7, wind_gusts_10m_max: 10, weather_codes: [0] }, units: { temperature: "°C", relative_humidity: "%", precipitation_probability: "%", precipitation: "mm", wind_speed: "km/h", wind_gusts: "km/h", elevation: "m" }, elevation_m: 330, caveats: [] },
  action_ids: ["try_top_location"], guidance: ["Start with the highest-ranked qualifying public location."],
  caveats: ["Recent public observations do not guarantee that the target will be present."], evidence_freshness_at: "2026-07-10T08:00:00", created_at: "2026-07-10T09:00:00Z",
};

export const targetBirdProfile: BirdProfile = {
  species_code: "target1", common_name: "Target Bird", scientific_name: "Avis target",
  taxonomic_category: "species", taxonomic_order: 1, order_name: "Passeriformes",
  family_common_name: "Target birds", family_scientific_name: "Targetidae",
  traits_status: "unavailable", mass_g: null, habitat: null,
  recent_public_observation_count: 0, latest_public_observation_at: null,
  photo: { status: "unavailable", source_record_id: null, species_name: null, display_url: null, source_url: null, creator: null, rights_holder: null, publisher: null, format: null, license_text: null, license_url: null, selection_reason: null, provider: null, license_code: null, original_width: null, original_height: null, caveats: ["Not enriched"], lookup_at: null },
  call: { status: "unavailable", source_record_id: null, recording_id: null, species_name: null, geographic_scope: null, recording_type: null, quality: null, recordist: null, locality: null, country: null, source_url: null, audio_url: null, license_text: null, license_url: null, selection_reason: null, caveats: ["Not enriched"], lookup_at: null },
  region_code: "US-AZ",
  taxonomy: { family_code: "target", report_as: null, extinct: false, extinct_year: null },
  traits: {
    status: "unavailable", source_scientific_name: null, avonet_family: null,
    avonet_order_name: null, avibase_id: null, inference: null, traits_inferred: null,
    reference_species: null, mass_source: null, mass_reference_other: null,
    sample: { total_individuals: null, female_individuals: null, male_individuals: null, unknown_sex_individuals: null, complete_measures: null },
    morphology: {
      beak_length_culmen_mm: null, beak_length_nares_mm: null, beak_width_mm: null,
      beak_depth_mm: null, tarsus_length_mm: null, wing_length_mm: null,
      kipps_distance_mm: null, secondary_length_mm: null, hand_wing_index: null,
      tail_length_mm: null, mass_g: null,
    },
    ecology: {
      habitat: null, habitat_density_code: null, habitat_density_label: null,
      migration_code: null, migration_label: null, trophic_level: null,
      trophic_niche: null, primary_lifestyle: null,
    },
    provenance: { dataset_doi: null, dataset_version: null, dataset_license: null, source_file_id: null, source_file_md5: null, loaded_at: null },
  },
  arizona_activity: {
    recent_public_observation_count: 0, latest_public_observation_at: null,
    public_location_count: 0, recent_public_notable_count: 0, top_public_locations: [],
  },
  gbif: { occurrence_count: 0, latest_event_date: null },
  xeno_canto: {
    recording_count: 0, latest_recording_date: null, representative_recording_id: null,
    representative_recordist: null, representative_recording_type: null,
    representative_recording_quality: null, representative_recording_license: null,
  },
  freshness: {
    species_list_loaded_at: "2026-07-10T08:00:00", taxonomy_loaded_at: "2026-07-10T08:00:00",
    ebird_observations_loaded_at: null, gbif_loaded_at: null, xeno_canto_loaded_at: null,
    catalog_freshness_at: "2026-07-10T08:00:00",
  },
};
