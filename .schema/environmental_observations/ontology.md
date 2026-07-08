# Ontology: environmental_observations

## Source artifacts read

- `.schema/environmental_observations/taxonomy.json`
- `.schema/environmental_observations/ebird_api.dbml`
- `.schema/environmental_observations/noaa_api.dbml`
- `.schema/environmental_observations/usgs_api.dbml`
- `.schema/environmental_observations/usgs_earthquakes_api.dbml`

## Summary

- Natural keys: none recorded in `taxonomy.json`; no cross-source stitching strategy required.
- Inferred structural relationships: included per user confirmation; all are marked `inferred=true`.
- dlt operational columns: included as attributes with `dlt metadata` notes per user confirmation.
- Semantic gaps: none identified from the confirmed taxonomy/use case.

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

eBird species codes, taxonomy, and alternate common/scientific/banding code rows present in the eBird schema.

### Source tables

| Pipeline | Table | Role |
|---|---|---|
| `ebird_api` | `taxonomy` | primary |
| `ebird_api` | `species_list` | secondary |
| `ebird_api` | `taxonomy__com_name_codes` | child |
| `ebird_api` | `taxonomy__sci_name_codes` | child |
| `ebird_api` | `taxonomy__banding_codes` | child |

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

### Relationships

| Relationship | Target | Via | Inferred |
|---|---|---|---|
| — | — | — | — |

### Assumptions

- No cross-source natural key/stitching strategy required.

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

## Assumptions & Exclusions

### Natural-key conflict strategies

- None required: no concept in `taxonomy.json` has a non-null `natural_key`.

### Relationship assumptions

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
