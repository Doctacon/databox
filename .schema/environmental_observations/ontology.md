# Ontology: environmental_observations

## Source artifacts read

- `.schema/environmental_observations/taxonomy.json`
- `.schema/environmental_observations/ebird_api.dbml`
- `.schema/environmental_observations/noaa_api.dbml`
- `.schema/environmental_observations/usgs_api.dbml`
- `.schema/environmental_observations/usgs_earthquakes_api.dbml`
- `.schema/environmental_observations/xeno_canto_api.dbml`
- `.schema/environmental_observations/gbif_api.dbml`
- `.schema/environmental_observations/avonet.dbml`

## Summary

- Natural keys: `Species.normalized_scientific_name` conforms eBird, GBIF, Xeno-canto, and AVONET species where a scientific-name key is available; `BirdSpeciesTraits.avibase_id` preserves the AVONET source identity.
- Inferred structural relationships: included per user confirmation; all are marked `inferred=true`.
- dlt operational columns: included as attributes with `dlt metadata` notes per user confirmation.
- Semantic gaps: none identified from the confirmed taxonomy/use case.
- GBIF occurrences and Xeno-canto recording metadata are modeled as separate fact entities that reference the conformed `Species` dimension when a normalized scientific-name key is available.
- AVONET traits remain global species-average measurements and categorical ecology, not Arizona-specific claims.

## BirdObservation

Individual eBird observation records with species, observation date/time, location, count, and region fields.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `ebird_api` | `recent_observations` | primary |
| `ebird_api` | `notable_observations` | secondary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `_dlt_id` | `text` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` | dlt metadata, not null, row_key, unique |
| `_dlt_load_id` | `text` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` | dlt metadata, not null |
| `_is_notable` | `bool` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `_loaded_at` | `timestamp` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `_observation_date` | `timestamp` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `_region_code` | `text` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `com_name` | `text` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `exotic_category` | `text` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `how_many` | `bigint` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `lat` | `double` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `lng` | `double` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `loc_id` | `text` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `loc_name` | `text` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `location_private` | `bool` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `obs_dt` | `timestamp` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `obs_reviewed` | `bool` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `obs_valid` | `bool` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `sci_name` | `text` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `species_code` | `text` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` |  |
| `sub_id` | `text` | `ebird_api.recent_observations`<br>`ebird_api.notable_observations` | not null, primary_key |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| OBSERVED_SPECIES | `Species` | `ebird_api.recent_observations.species_code -> ebird_api.taxonomy/species_list.species_code` | true |
| OBSERVED_SPECIES | `Species` | `ebird_api.notable_observations.species_code -> ebird_api.taxonomy/species_list.species_code` | true |
| OBSERVED_AT | `BirdHotspot` | `ebird_api.recent_observations.loc_id -> ebird_api.hotspots.loc_id` | true |
| OBSERVED_AT | `BirdHotspot` | `ebird_api.notable_observations.loc_id -> ebird_api.hotspots.loc_id` | true |

### Assumptions

- No cross-source natural key/stitching strategy required.

## Species

Conformed bird species/taxon concept across eBird taxonomy/species lists, GBIF occurrence taxonomy, Xeno-canto recording metadata, and AVONET species-trait identity.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `ebird_api` | `taxonomy` | primary |
| `ebird_api` | `species_list` | secondary |
| `ebird_api` | `taxonomy__com_name_codes` | child |
| `ebird_api` | `taxonomy__sci_name_codes` | child |
| `ebird_api` | `taxonomy__banding_codes` | child |
| `xeno_canto_api` | `recordings` | media_context |
| `gbif_api` | `occurrences` | secondary_taxonomy |
| `avonet` | `species_traits` | trait_context |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `_dlt_id` | `text` | `ebird_api.taxonomy`<br>`ebird_api.species_list`<br>`ebird_api.taxonomy__com_name_codes`<br>`ebird_api.taxonomy__sci_name_codes`<br>`ebird_api.taxonomy__banding_codes` | dlt metadata, not null, row_key, unique |
| `_dlt_list_idx` | `bigint` | `ebird_api.taxonomy__com_name_codes`<br>`ebird_api.taxonomy__sci_name_codes`<br>`ebird_api.taxonomy__banding_codes` | dlt metadata, not null |
| `_dlt_load_id` | `text` | `ebird_api.taxonomy`<br>`ebird_api.species_list` | dlt metadata, not null |
| `_dlt_parent_id` | `text` | `ebird_api.taxonomy__com_name_codes`<br>`ebird_api.taxonomy__sci_name_codes`<br>`ebird_api.taxonomy__banding_codes` | dlt metadata, not null |
| `_loaded_at` | `timestamp` | `ebird_api.taxonomy`<br>`ebird_api.species_list` |  |
| `banding_code_value` | `text` | `ebird_api.taxonomy__banding_codes` | source column: taxonomy__banding_codes.value |
| `category` | `text` | `ebird_api.taxonomy` |  |
| `com_name` | `text` | `ebird_api.taxonomy` |  |
| `com_name_code_value` | `text` | `ebird_api.taxonomy__com_name_codes` | source column: taxonomy__com_name_codes.value |
| `extinct` | `bool` | `ebird_api.taxonomy` |  |
| `extinct_year` | `bigint` | `ebird_api.taxonomy` |  |
| `family_code` | `text` | `ebird_api.taxonomy` |  |
| `family_com_name` | `text` | `ebird_api.taxonomy` |  |
| `family_sci_name` | `text` | `ebird_api.taxonomy` |  |
| `order` | `text` | `ebird_api.taxonomy`<br>`ebird_api.species_list` | also type bigint in ebird_api.species_list |
| `region` | `text` | `ebird_api.species_list` |  |
| `report_as` | `text` | `ebird_api.taxonomy` |  |
| `sci_name` | `text` | `ebird_api.taxonomy` | not null, primary_key |
| `sci_name_code_value` | `text` | `ebird_api.taxonomy__sci_name_codes` | source column: taxonomy__sci_name_codes.value |
| `species_code` | `text` | `ebird_api.taxonomy`<br>`ebird_api.species_list` | not null, primary_key |
| `taxon_order` | `double` | `ebird_api.taxonomy` |  |
| `accepted_scientific_name` | `text` | `gbif_api.occurrences` | GBIF species conformance source column |
| `vernacular_name` | `text` | `gbif_api.occurrences` | GBIF common-name fallback |
| `taxon_key` | `bigint` | `gbif_api.occurrences` | GBIF taxon identifier |
| `accepted_taxon_key` | `bigint` | `gbif_api.occurrences` | GBIF accepted taxon identifier |
| `genus` | `text` | `gbif_api.occurrences`<br>`xeno_canto_api.recordings` | GBIF/Xeno-canto species conformance source column |
| `english_name` | `text` | `xeno_canto_api.recordings` | Xeno-canto common-name/media context |
| `recording_url` | `text` | `xeno_canto_api.recordings` | Xeno-canto external recording link |
| `audio_file_url` | `text` | `xeno_canto_api.recordings` | Xeno-canto external media link; audio not downloaded |
| `license` | `text` | `gbif_api.occurrences`<br>`xeno_canto_api.recordings` | License/provenance context |
| `source_scientific_name` | `text` | `avonet.species_traits` | AVONET source scientific name used only for governed exact normalization. |
| `avibase_id` | `text` | `avonet.species_traits` | AVONET source identifier; primary key at the raw trait grain. |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| — | — | — | — |

### Assumptions

- Natural key: `normalized_scientific_name` from eBird `sci_name`, GBIF `accepted_scientific_name`/`scientific_name`/`species`, Xeno-canto `genus || ' ' || species`, and AVONET `source_scientific_name`; normalization lowercases, trims, and strips trailing parenthetical authorship.
- eBird wins descriptive conflicts; GBIF fills taxon identifiers/gaps; Xeno-canto supplies media context; AVONET supplies species-average trait context only after an exact governed match.
- Coverage is a union of species from any source; source rows without a usable scientific-name key remain source-scoped.

## BirdSpeciesTraits

AVONET v7 eBird-aligned species-average morphology, ecology, measurement provenance, and pinned dataset provenance.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `avonet` | `species_traits` | primary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `source_scientific_name` | `text` | `avonet.species_traits` | Source scientific name for exact conformance; not an Arizona-range claim. |
| `family` | `text` | `avonet.species_traits` | AVONET taxonomic family. |
| `order_name` | `text` | `avonet.species_traits` | AVONET taxonomic order. |
| `avibase_id` | `text` | `avonet.species_traits` | not null, primary_key |
| `total_individuals` | `bigint` | `avonet.species_traits` | Contributing-individual count. |
| `female_individuals` | `bigint` | `avonet.species_traits` | Identified-female count. |
| `male_individuals` | `bigint` | `avonet.species_traits` | Identified-male count. |
| `unknown_sex_individuals` | `bigint` | `avonet.species_traits` | Unknown-sex count. |
| `complete_measures` | `bigint` | `avonet.species_traits` | Complete-measurement count. |
| `beak_length_culmen_mm` | `double` | `avonet.species_traits` | millimetres |
| `beak_length_nares_mm` | `double` | `avonet.species_traits` | millimetres |
| `beak_width_mm` | `double` | `avonet.species_traits` | millimetres |
| `beak_depth_mm` | `double` | `avonet.species_traits` | millimetres |
| `tarsus_length_mm` | `double` | `avonet.species_traits` | millimetres |
| `wing_length_mm` | `double` | `avonet.species_traits` | millimetres |
| `kipps_distance_mm` | `double` | `avonet.species_traits` | millimetres |
| `secondary_length_mm` | `double` | `avonet.species_traits` | millimetres |
| `hand_wing_index` | `double` | `avonet.species_traits` | Dimensionless index. |
| `tail_length_mm` | `double` | `avonet.species_traits` | millimetres |
| `mass_g` | `double` | `avonet.species_traits` | grams |
| `mass_source` | `text` | `avonet.species_traits` | Exact AVONET categorical value. |
| `mass_reference_other` | `text` | `avonet.species_traits` | Other source citation when supplied. |
| `inference` | `bool` | `avonet.species_traits` | True only for source value YES. |
| `traits_inferred` | `text` | `avonet.species_traits` | Exact semicolon-delimited source list. |
| `reference_species` | `text` | `avonet.species_traits` | Source species used for inference. |
| `habitat` | `text` | `avonet.species_traits` | Exact habitat category. |
| `habitat_density_code` | `bigint` | `avonet.species_traits` | 1 dense; 2 semi-open; 3 open. |
| `migration_code` | `bigint` | `avonet.species_traits` | 1 sedentary; 2 partial migrant; 3 migratory. |
| `trophic_level` | `text` | `avonet.species_traits` | Exact trophic-level category. |
| `trophic_niche` | `text` | `avonet.species_traits` | Exact trophic-niche category. |
| `primary_lifestyle` | `text` | `avonet.species_traits` | Exact primary-lifestyle category. |
| `dataset_doi` | `text` | `avonet.species_traits` | `10.6084/m9.figshare.16586228.v7` |
| `dataset_version` | `text` | `avonet.species_traits` | `v7` |
| `dataset_license` | `text` | `avonet.species_traits` | `CC BY 4.0` |
| `source_file_id` | `bigint` | `avonet.species_traits` | `34480856` |
| `source_file_md5` | `text` | `avonet.species_traits` | Validated pinned workbook MD5. |
| `source_url` | `text` | `avonet.species_traits` | Fixed Figshare URL; signed redirect omitted. |
| `loaded_at` | `timestamp` | `avonet.species_traits` | Snapshot load timestamp. |
| `_dlt_load_id` | `text` | `avonet.species_traits` | dlt metadata, not null |
| `_dlt_id` | `text` | `avonet.species_traits` | dlt metadata, not null, row_key, unique |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| DESCRIBES_SPECIES | `Species` | `avonet.species_traits.source_scientific_name -> Species.normalized_scientific_name` after governed normalization | true |

### Assumptions

- Natural key at the source grain is `avibase_id`; scientific names and Avibase IDs are independently unique in the pinned worksheet.
- Blank and exact `NA` values are null; categorical/code values otherwise remain exact.
- Traits are global AVONET species averages and MUST NOT be represented as Arizona-specific range or phenotype claims.
- No taxonomy mapping is guessed during ingestion; the modeled exact normalized-name join is separately governed.
- The authoritative table is published only after a complete Quack staging load passes exact row, unique-key, column, and metadata validation; transient staging is not a business entity.

## BirdHotspot

eBird hotspot location records with hotspot id, name, lat/lng, region codes, and observation/checklist totals.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `ebird_api` | `hotspots` | primary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `_dlt_id` | `text` | `ebird_api.hotspots` | dlt metadata, not null, row_key, unique |
| `_dlt_load_id` | `text` | `ebird_api.hotspots` | dlt metadata, not null |
| `_loaded_at` | `timestamp` | `ebird_api.hotspots` |  |
| `_region_code` | `text` | `ebird_api.hotspots` |  |
| `country_code` | `text` | `ebird_api.hotspots` |  |
| `lat` | `double` | `ebird_api.hotspots` |  |
| `latest_obs_dt` | `timestamp` | `ebird_api.hotspots` |  |
| `lng` | `double` | `ebird_api.hotspots` |  |
| `loc_id` | `text` | `ebird_api.hotspots` | not null, primary_key |
| `loc_name` | `text` | `ebird_api.hotspots` |  |
| `num_checklists_all_time` | `bigint` | `ebird_api.hotspots` |  |
| `num_species_all_time` | `bigint` | `ebird_api.hotspots` |  |
| `subnational1_code` | `text` | `ebird_api.hotspots` |  |
| `subnational2_code` | `text` | `ebird_api.hotspots` |  |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| — | — | — | — |

### Assumptions

- No cross-source natural key/stitching strategy required.

## RegionDailyStats

Daily eBird regional counts for checklists, contributors, and species by region and date parts.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `ebird_api` | `region_stats` | primary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `_dlt_id` | `text` | `ebird_api.region_stats` | dlt metadata, not null, row_key, unique |
| `_dlt_load_id` | `text` | `ebird_api.region_stats` | dlt metadata, not null |
| `_loaded_at` | `timestamp` | `ebird_api.region_stats` |  |
| `date` | `text` | `ebird_api.region_stats` |  |
| `day` | `bigint` | `ebird_api.region_stats` | not null, primary_key |
| `month` | `bigint` | `ebird_api.region_stats` | not null, primary_key |
| `num_checklists` | `bigint` | `ebird_api.region_stats` |  |
| `num_contributors` | `bigint` | `ebird_api.region_stats` |  |
| `num_species` | `bigint` | `ebird_api.region_stats` |  |
| `region_code` | `text` | `ebird_api.region_stats` | not null, primary_key |
| `year` | `bigint` | `ebird_api.region_stats` | not null, primary_key |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| — | — | — | — |

### Assumptions

- No cross-source natural key/stitching strategy required.

## WeatherObservation

NOAA daily weather observation values by date, datatype, station, value, and source fields.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `noaa_api` | `daily_weather` | primary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `_dlt_id` | `text` | `noaa_api.daily_weather` | dlt metadata, not null, row_key, unique |
| `_dlt_load_id` | `text` | `noaa_api.daily_weather` | dlt metadata, not null |
| `_loaded_at` | `timestamp` | `noaa_api.daily_weather` |  |
| `_location_id` | `text` | `noaa_api.daily_weather` |  |
| `attributes` | `text` | `noaa_api.daily_weather` |  |
| `datatype` | `text` | `noaa_api.daily_weather` | not null, primary_key |
| `date` | `text` | `noaa_api.daily_weather` | not null, primary_key |
| `source` | `text` | `noaa_api.daily_weather` |  |
| `station` | `text` | `noaa_api.daily_weather` | not null, primary_key |
| `value` | `double` | `noaa_api.daily_weather` |  |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| OBSERVED_AT | `WeatherStation` | `noaa_api.daily_weather.station -> noaa_api.stations.id` | true |

### Assumptions

- No cross-source natural key/stitching strategy required.

## WeatherStation

NOAA station metadata with station id, name, lat/lng, elevation, and coverage dates.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `noaa_api` | `stations` | primary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `_dlt_id` | `text` | `noaa_api.stations` | dlt metadata, not null, row_key, unique |
| `_dlt_load_id` | `text` | `noaa_api.stations` | dlt metadata, not null |
| `_loaded_at` | `timestamp` | `noaa_api.stations` |  |
| `_location_id` | `text` | `noaa_api.stations` |  |
| `datacoverage` | `double` | `noaa_api.stations` |  |
| `elevation` | `double` | `noaa_api.stations` |  |
| `elevation_unit` | `text` | `noaa_api.stations` |  |
| `id` | `text` | `noaa_api.stations` | not null, primary_key |
| `latitude` | `double` | `noaa_api.stations` |  |
| `longitude` | `double` | `noaa_api.stations` |  |
| `maxdate` | `text` | `noaa_api.stations` |  |
| `mindate` | `text` | `noaa_api.stations` |  |
| `name` | `text` | `noaa_api.stations` |  |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| — | — | — | — |

### Assumptions

- No cross-source natural key/stitching strategy required.

## StreamflowObservation

USGS daily water values by site, parameter code, observation date, value, and unit fields.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `usgs_api` | `daily_values` | primary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `_dlt_id` | `text` | `usgs_api.daily_values` | dlt metadata, not null, row_key, unique |
| `_dlt_load_id` | `text` | `usgs_api.daily_values` | dlt metadata, not null |
| `_loaded_at` | `timestamp` | `usgs_api.daily_values` |  |
| `_state_cd` | `text` | `usgs_api.daily_values` |  |
| `latitude` | `double` | `usgs_api.daily_values` |  |
| `longitude` | `double` | `usgs_api.daily_values` |  |
| `observation_date` | `text` | `usgs_api.daily_values` | not null, primary_key |
| `parameter_cd` | `text` | `usgs_api.daily_values` | not null, primary_key |
| `parameter_name` | `text` | `usgs_api.daily_values` |  |
| `qualifier` | `text` | `usgs_api.daily_values` |  |
| `site_name` | `text` | `usgs_api.daily_values` |  |
| `site_no` | `text` | `usgs_api.daily_values` | not null, primary_key |
| `unit_cd` | `text` | `usgs_api.daily_values` |  |
| `value` | `double` | `usgs_api.daily_values` |  |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| OBSERVED_AT | `StreamgageSite` | `usgs_api.daily_values.site_no -> usgs_api.sites.site_no` | true |

### Assumptions

- No cross-source natural key/stitching strategy required.

## StreamgageSite

USGS site metadata with site number, name, lat/lng, hydrologic unit, drainage area, and state/county codes.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `usgs_api` | `sites` | primary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `_dlt_id` | `text` | `usgs_api.sites` | dlt metadata, not null, row_key, unique |
| `_dlt_load_id` | `text` | `usgs_api.sites` | dlt metadata, not null |
| `_loaded_at` | `timestamp` | `usgs_api.sites` |  |
| `begin_date` | `text` | `usgs_api.sites` |  |
| `county_cd` | `text` | `usgs_api.sites` |  |
| `drain_area_va` | `double` | `usgs_api.sites` |  |
| `end_date` | `text` | `usgs_api.sites` |  |
| `huc_cd` | `text` | `usgs_api.sites` |  |
| `latitude` | `double` | `usgs_api.sites` |  |
| `longitude` | `double` | `usgs_api.sites` |  |
| `site_name` | `text` | `usgs_api.sites` |  |
| `site_no` | `text` | `usgs_api.sites` | not null, primary_key |
| `site_type` | `text` | `usgs_api.sites` |  |
| `state_cd` | `text` | `usgs_api.sites` |  |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| — | — | — | — |

### Assumptions

- No cross-source natural key/stitching strategy required.

## EarthquakeEvent

USGS earthquake event records with id, magnitude, event time, location coordinates, depth, status, and event type fields.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `usgs_earthquakes_api` | `events` | primary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `_dlt_id` | `text` | `usgs_earthquakes_api.events` | dlt metadata, not null, row_key, unique |
| `_dlt_load_id` | `text` | `usgs_earthquakes_api.events` | dlt metadata, not null |
| `_loaded_at` | `timestamp` | `usgs_earthquakes_api.events` |  |
| `alert` | `text` | `usgs_earthquakes_api.events` |  |
| `depth_km` | `double` | `usgs_earthquakes_api.events` |  |
| `event_time` | `text` | `usgs_earthquakes_api.events` |  |
| `event_type` | `text` | `usgs_earthquakes_api.events` |  |
| `event_updated_at` | `text` | `usgs_earthquakes_api.events` |  |
| `id` | `text` | `usgs_earthquakes_api.events` | not null, primary_key |
| `latitude` | `double` | `usgs_earthquakes_api.events` |  |
| `longitude` | `double` | `usgs_earthquakes_api.events` |  |
| `magnitude` | `double` | `usgs_earthquakes_api.events` |  |
| `magnitude_type` | `text` | `usgs_earthquakes_api.events` |  |
| `place` | `text` | `usgs_earthquakes_api.events` |  |
| `significance` | `bigint` | `usgs_earthquakes_api.events` |  |
| `status` | `text` | `usgs_earthquakes_api.events` |  |
| `title` | `text` | `usgs_earthquakes_api.events` |  |
| `tsunami_flag` | `bigint` | `usgs_earthquakes_api.events` |  |
| `url` | `text` | `usgs_earthquakes_api.events` |  |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| — | — | — | — |

### Assumptions

- No cross-source natural key/stitching strategy required.

## BirdOccurrence

GBIF bird occurrence records with occurrence identifiers, taxonomy fields, event date parts, coordinates, location/status fields, license, and provenance metadata.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `gbif_api` | `occurrences` | primary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `key` | `bigint` | `gbif_api.occurrences` | not null, primary_key |
| `gbif_id` | `text` | `gbif_api.occurrences` |   |
| `occurrence_id` | `text` | `gbif_api.occurrences` |   |
| `dataset_key` | `text` | `gbif_api.occurrences` |   |
| `publishing_org_key` | `text` | `gbif_api.occurrences` |   |
| `installation_key` | `text` | `gbif_api.occurrences` |   |
| `hosting_organization_key` | `text` | `gbif_api.occurrences` |   |
| `protocol` | `text` | `gbif_api.occurrences` |   |
| `publishing_country` | `text` | `gbif_api.occurrences` |   |
| `scientific_name` | `text` | `gbif_api.occurrences` |   |
| `accepted_scientific_name` | `text` | `gbif_api.occurrences` |   |
| `vernacular_name` | `text` | `gbif_api.occurrences` |   |
| `kingdom` | `text` | `gbif_api.occurrences` |   |
| `phylum` | `text` | `gbif_api.occurrences` |   |
| `class_name` | `text` | `gbif_api.occurrences` |   |
| `order_name` | `text` | `gbif_api.occurrences` |   |
| `family` | `text` | `gbif_api.occurrences` |   |
| `genus` | `text` | `gbif_api.occurrences` |   |
| `species` | `text` | `gbif_api.occurrences` |   |
| `generic_name` | `text` | `gbif_api.occurrences` |   |
| `specific_epithet` | `text` | `gbif_api.occurrences` |   |
| `taxon_rank` | `text` | `gbif_api.occurrences` |   |
| `taxon_key` | `bigint` | `gbif_api.occurrences` |   |
| `accepted_taxon_key` | `bigint` | `gbif_api.occurrences` |   |
| `kingdom_key` | `bigint` | `gbif_api.occurrences` |   |
| `phylum_key` | `bigint` | `gbif_api.occurrences` |   |
| `class_key` | `bigint` | `gbif_api.occurrences` |   |
| `order_key` | `bigint` | `gbif_api.occurrences` |   |
| `family_key` | `bigint` | `gbif_api.occurrences` |   |
| `genus_key` | `bigint` | `gbif_api.occurrences` |   |
| `species_key` | `bigint` | `gbif_api.occurrences` |   |
| `decimal_latitude` | `double` | `gbif_api.occurrences` |   |
| `decimal_longitude` | `double` | `gbif_api.occurrences` |   |
| `coordinate_uncertainty_in_meters` | `double` | `gbif_api.occurrences` |   |
| `country` | `text` | `gbif_api.occurrences` |   |
| `country_code` | `text` | `gbif_api.occurrences` |   |
| `state_province` | `text` | `gbif_api.occurrences` |   |
| `locality` | `text` | `gbif_api.occurrences` |   |
| `event_date` | `text` | `gbif_api.occurrences` |   |
| `year` | `bigint` | `gbif_api.occurrences` |   |
| `month` | `bigint` | `gbif_api.occurrences` |   |
| `day` | `bigint` | `gbif_api.occurrences` |   |
| `basis_of_record` | `text` | `gbif_api.occurrences` |   |
| `occurrence_status` | `text` | `gbif_api.occurrences` |   |
| `establishment_means` | `text` | `gbif_api.occurrences` |   |
| `record_number` | `text` | `gbif_api.occurrences` |   |
| `recorded_by` | `text` | `gbif_api.occurrences` |   |
| `identified_by` | `text` | `gbif_api.occurrences` |   |
| `institution_code` | `text` | `gbif_api.occurrences` |   |
| `collection_code` | `text` | `gbif_api.occurrences` |   |
| `catalog_number` | `text` | `gbif_api.occurrences` |   |
| `license` | `text` | `gbif_api.occurrences` |   |
| `references` | `text` | `gbif_api.occurrences` |   |
| `last_interpreted` | `text` | `gbif_api.occurrences` |   |
| `last_crawled` | `text` | `gbif_api.occurrences` |   |
| `last_parsed` | `text` | `gbif_api.occurrences` |   |
| `_source_url` | `text` | `gbif_api.occurrences` |   |
| `_query_country_code` | `text` | `gbif_api.occurrences` |   |
| `_query_state_province` | `text` | `gbif_api.occurrences` |   |
| `_query_taxon_key` | `bigint` | `gbif_api.occurrences` |   |
| `_loaded_at` | `timestamp` | `gbif_api.occurrences` |   |
| `_dlt_load_id` | `text` | `gbif_api.occurrences` | dlt metadata, not null |
| `_dlt_id` | `text` | `gbif_api.occurrences` | dlt metadata, not null, row_key, unique |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| — | — | — | — |

### Assumptions

- No cross-source natural key/stitching strategy required.

## BirdSoundRecording

Xeno-canto bird sound recording metadata with recording identifiers, species names, media links, license/attribution fields, date/location fields, and provenance metadata.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `xeno_canto_api` | `recordings` | primary |

### Attributes

| Name | Type | Source | Notes |
|---|---|---|---|
| `id` | `text` | `xeno_canto_api.recordings` | not null, primary_key |
| `genus` | `text` | `xeno_canto_api.recordings` |   |
| `species` | `text` | `xeno_canto_api.recordings` |   |
| `subspecies` | `text` | `xeno_canto_api.recordings` |   |
| `group_name` | `text` | `xeno_canto_api.recordings` |   |
| `english_name` | `text` | `xeno_canto_api.recordings` |   |
| `recordist` | `text` | `xeno_canto_api.recordings` |   |
| `country` | `text` | `xeno_canto_api.recordings` |   |
| `locality` | `text` | `xeno_canto_api.recordings` |   |
| `latitude` | `double` | `xeno_canto_api.recordings` |   |
| `longitude` | `double` | `xeno_canto_api.recordings` |   |
| `altitude` | `text` | `xeno_canto_api.recordings` |   |
| `recording_type` | `text` | `xeno_canto_api.recordings` |   |
| `sex` | `text` | `xeno_canto_api.recordings` |   |
| `stage` | `text` | `xeno_canto_api.recordings` |   |
| `method` | `text` | `xeno_canto_api.recordings` |   |
| `recording_url` | `text` | `xeno_canto_api.recordings` |   |
| `audio_file_url` | `text` | `xeno_canto_api.recordings` |   |
| `file_name` | `text` | `xeno_canto_api.recordings` |   |
| `sonogram` | `text` | `xeno_canto_api.recordings` |   |
| `oscillogram` | `text` | `xeno_canto_api.recordings` |   |
| `license` | `text` | `xeno_canto_api.recordings` |   |
| `quality` | `text` | `xeno_canto_api.recordings` |   |
| `length` | `text` | `xeno_canto_api.recordings` |   |
| `recording_time` | `text` | `xeno_canto_api.recordings` |   |
| `recording_date` | `text` | `xeno_canto_api.recordings` |   |
| `uploaded_at` | `text` | `xeno_canto_api.recordings` |   |
| `also_species` | `text` | `xeno_canto_api.recordings` |   |
| `remarks` | `text` | `xeno_canto_api.recordings` |   |
| `bird_seen` | `text` | `xeno_canto_api.recordings` |   |
| `animal_seen` | `text` | `xeno_canto_api.recordings` |   |
| `playback_used` | `text` | `xeno_canto_api.recordings` |   |
| `temperature` | `text` | `xeno_canto_api.recordings` |   |
| `registration_number` | `text` | `xeno_canto_api.recordings` |   |
| `automatic_recording` | `text` | `xeno_canto_api.recordings` |   |
| `device` | `text` | `xeno_canto_api.recordings` |   |
| `microphone` | `text` | `xeno_canto_api.recordings` |   |
| `_source_url` | `text` | `xeno_canto_api.recordings` |   |
| `_query` | `text` | `xeno_canto_api.recordings` |   |
| `_query_page` | `bigint` | `xeno_canto_api.recordings` |   |
| `_loaded_at` | `timestamp` | `xeno_canto_api.recordings` |   |
| `_dlt_load_id` | `text` | `xeno_canto_api.recordings` | dlt metadata, not null |
| `_dlt_id` | `text` | `xeno_canto_api.recordings` | dlt metadata, not null, row_key, unique |

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| — | — | — | — |

### Assumptions

- No cross-source natural key/stitching strategy required.
- Audio remains an external linked artifact; CDM stores metadata and URLs only.

## Assumptions & Exclusions

### Natural-key conflict strategies

- `Species`: conform all eBird, GBIF, and Xeno-canto species using normalized scientific name (lowercase/trim/strip trailing parenthetical authorship); eBird wins descriptive conflicts, GBIF fills taxon identifiers/gaps, Xeno-canto supplies media context; coverage is a union.

### Relationship assumptions

- `Species` STITCHED_BY `Species` via `normalized_scientific_name`.

- Inferred key-column relationships were included after user confirmation.
- `BirdObservation` OBSERVED_SPECIES `Species` via `ebird_api.recent_observations.species_code -> ebird_api.taxonomy/species_list.species_code`.
- `BirdObservation` OBSERVED_SPECIES `Species` via `ebird_api.notable_observations.species_code -> ebird_api.taxonomy/species_list.species_code`.
- `BirdObservation` OBSERVED_AT `BirdHotspot` via `ebird_api.recent_observations.loc_id -> ebird_api.hotspots.loc_id`.
- `BirdObservation` OBSERVED_AT `BirdHotspot` via `ebird_api.notable_observations.loc_id -> ebird_api.hotspots.loc_id`.
- `WeatherObservation` OBSERVED_AT `WeatherStation` via `noaa_api.daily_weather.station -> noaa_api.stations.id`.
- `StreamflowObservation` OBSERVED_AT `StreamgageSite` via `usgs_api.daily_values.site_no -> usgs_api.sites.site_no`.

### Semantic gaps

- None identified from the stated use case and confirmed taxonomy.

### Excluded tables

| Pipeline | Table | Reason |
|---|---|---|
| `ebird_api` | `_dlt_version` | dlt internal schema version table |
| `ebird_api` | `_dlt_loads` | dlt internal load tracking table |
| `ebird_api` | `_dlt_pipeline_state` | dlt internal pipeline state table |
| `noaa_api` | `_dlt_version` | dlt internal schema version table |
| `noaa_api` | `_dlt_loads` | dlt internal load tracking table |
| `noaa_api` | `_dlt_pipeline_state` | dlt internal pipeline state table |
| `noaa_api` | `datasets` | NOAA source dataset metadata, not a date/location observation or location entity |
| `usgs_api` | `_dlt_version` | dlt internal schema version table |
| `usgs_api` | `_dlt_loads` | dlt internal load tracking table |
| `usgs_api` | `_dlt_pipeline_state` | dlt internal pipeline state table |
| `usgs_earthquakes_api` | `_dlt_version` | dlt internal schema version table |
| `usgs_earthquakes_api` | `_dlt_loads` | dlt internal load tracking table |
| `usgs_earthquakes_api` | `_dlt_pipeline_state` | dlt internal pipeline state table |
| `gbif_api` | `_dlt_version` | dlt internal schema version table |
| `gbif_api` | `_dlt_loads` | dlt internal load tracking table |
| `xeno_canto_api` | `_dlt_version` | dlt internal schema version table |
| `xeno_canto_api` | `_dlt_loads` | dlt internal load tracking table |
