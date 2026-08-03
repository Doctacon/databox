export interface PublicBounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface PublicSpeciesSummary {
  species_code: string;
  common_name: string | null;
  scientific_name: string | null;
  profile_path: string;
  hero_photo: PublicMedia | null;
  photo_count: number;
}

export interface PublicCellSummary {
  cell_id: string;
  path: string;
  observation_count: number;
  bounds: PublicBounds;
}

export interface PublicPlacePrefix {
  prefix: string;
  path: string;
  count: number;
}

export interface PublicManifest {
  schema_version: 1;
  mode: "public";
  release_mode: "synthetic" | "production";
  generated_at: string;
  data_version: string;
  region: {
    code: "US-AZ";
    name: string;
    bounds: PublicBounds;
  };
  species: PublicSpeciesSummary[];
  cells: PublicCellSummary[];
  place_prefixes: PublicPlacePrefix[];
  attribution_path: string;
  source_policy: {
    direct_ebird: "excluded";
    occurrence_source: "synthetic" | "gbif";
    gbif_dataset_key: string | null;
    coverage: "fictional_fixture" | "bounded_sample";
    required_taxon_key: number | null;
    media_source: "none" | "usfws";
    media_delivery: "none" | "immutable_r2";
  };
  license_policy: {
    version: 1;
    allowed: Record<string, string[]>;
    rejected_counts: Record<string, number>;
  };
  counts: {
    species: number;
    observations: number;
    places: number;
    attribution_items: number;
    media_items: number;
    species_with_media: number;
  };
}

/** Small mutable pointer published last after an immutable R2 release is complete. */
export interface PublicReleasePointer {
  schema_version: 1;
  mode: "public-release-pointer";
  release_id: string;
  data_version: string;
  published_at: string;
  manifest_path: string;
  manifest_sha256: string;
  release_manifest_sha256: string;
  release_manifest_key: string;
  asset_base_key: string;
  file_count: number;
  total_bytes: number;
  previous_releases: unknown[];
}

export interface PublicMedia {
  kind: "photo";
  provider: "usfws";
  media_id: string;
  url: string;
  source_url: string;
  creator: string;
  license: string;
  license_url: string;
  attribution_id: string;
  scientific_name: string;
  title: string;
  caption: string | null;
  alt_text: string;
  width: number;
  height: number;
  mime_type: "image/jpeg" | "image/png" | "image/webp";
  sha256: string;
}

export interface PublicSpeciesProfile {
  schema_version: 1;
  species_code: string;
  common_name: string | null;
  scientific_name: string | null;
  taxonomic_category: string;
  family: { common_name: string | null; scientific_name: string | null };
  order_name: string | null;
  traits: Record<string, string | number | boolean | null>;
  evidence: {
    licensed_occurrence_count: number;
    latest_licensed_occurrence_at: string | null;
  };
  media: PublicMedia[];
}

export interface PublicObservation {
  public_id: string;
  species_code: string;
  observed_at: string;
  count: number | null;
  count_display: string;
  is_notable: boolean;
  source: "synthetic" | "gbif";
  attribution_id: string;
  location: {
    name: string;
    latitude: number;
    longitude: number;
    kind: string;
    timezone: "America/Phoenix" | "America/Denver" | null;
    timezone_source: string;
  };
}

export interface PublicCell {
  schema_version: 1;
  cell_id: string;
  bounds: PublicBounds;
  observations: PublicObservation[];
}

export interface PublicPlace {
  public_id: string;
  name: string;
  kind: string;
  source: "synthetic" | "usgs_gnis";
  latitude: number;
  longitude: number;
  timezone: "America/Phoenix" | "America/Denver" | null;
  timezone_source: string;
}

export interface PublicPlaceShard {
  schema_version: 1;
  prefix: string;
  places: PublicPlace[];
}

export interface PublicAttributionSource {
  provider: string;
  title: string;
  url: string;
  license: string;
  license_url: string | null;
  credit: string;
  modifications?: string;
  disclaimer?: string;
}

export interface PublicAttribution {
  schema_version: 1;
  generated_at: string;
  sources: PublicAttributionSource[];
  items: Array<{
    attribution_id: string;
    provider: string;
    source_url: string;
    creator: string;
    license: string;
    license_url: string;
    dataset_title?: string;
    dataset_key?: string;
    publisher?: string;
    dataset_citation?: string;
    dataset_doi?: string;
  }>;
}

export interface PublicWatch {
  id: string;
  species_code: string;
  bird_name: string;
  center_name: string;
  center_latitude: number;
  center_longitude: number;
  center_timezone: "America/Phoenix" | "America/Denver";
  radius_miles: number;
  outing_date: string;
  created_at: string;
}

export interface WatchMatch extends PublicObservation {
  distance_miles: number;
}

export interface WatchEvaluation {
  watch: PublicWatch;
  matches: WatchMatch[];
  evaluated_at: string;
  loaded_cell_ids: string[];
}
