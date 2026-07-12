Status: done
Created: 2026-07-11
Updated: 2026-07-11

# Rufous place search and Field Map interaction research

## Question

How should Rufous support birding/natural-place suggestions such as Watson Lake, reuse them for personal observations, and repair Field Map interaction without adding proprietary services or violating local privacy?

## Sources and methods

Inspected the current Open-Meteo city geocoder, location combobox, trip/target/Watch contracts, personal observation schema/forms, Field Map lifecycle/style/layout, active local/privacy decisions, and read-only DuckDB state.

Live local findings:

- `environmental_observations.dim_bird_hotspot` contains 2,912 unique Arizona hotspots.
- It includes exact source location `L270303`, “Watson Lake and Riparian Preserve,” at 34.5822319, -112.4259328.
- Current Field Map initializes an empty clustered source, attempts `setData` before the style/source is guaranteed loaded, and does not retry on `load`; this explains the boundary-only map.
- Selected Encounter is outside `.field-map-layout`, causing it to fall below rather than occupy the right rail.

External sources:

- Overture Places guide/schema/access/release calendar: https://docs.overturemaps.org/guides/places/, https://docs.overturemaps.org/schema/reference/places/place/, https://docs.overturemaps.org/getting-data/duckdb/, https://docs.overturemaps.org/release-calendar/
- Overture Base water and attribution: https://docs.overturemaps.org/schema/reference/base/water/ and https://docs.overturemaps.org/attribution/
- Nominatim import/search and natural-feature layers: https://nominatim.org/release-docs/latest/admin/Import/ and https://nominatim.org/release-docs/develop/api/Search/
- Arizona OpenStreetMap extract: https://download.geofabrik.de/north-america/us/arizona.html
- GeoNames feature codes/export: https://www.geonames.org/export/codes.html and https://download.geonames.org/export/dump/readme.txt

## Findings

1. Existing local eBird hotspots are the highest-value first source for birding workflows and already solve the reported Watson Lake case without a new ingestion pipeline, runtime network request, or licensing family.
2. Overture Places is point-centric toward facilities/businesses/amenities. Named water requires a separate Base water query, mostly OSM-derived data, attribution handling, release/schema churn, roughly 60-day release retention, and per-source Places licenses. It is viable later but not the smallest solution.
3. A local OSM/Nominatim stack covers broad natural features but adds a regional PBF import, ODbL obligations, PostgreSQL/search infrastructure, and update operations disproportionate to the immediate need.
4. GeoNames is lightweight and CC BY 4.0 but did not surface the Prescott Watson Lake example in retrieved evidence and is less birding-specific.
5. Merge local hotspot results first with the existing Open-Meteo city fallback. Token-order-independent matching lets `lake watson` match `Watson Lake and Riparian Preserve`. Suggestions must identify source/type visibly and in strict API data.
6. Personal observation locations need explicit structured selection to preserve coordinates/source identity. Free text remains useful for private notes and legacy data; editing selected text must clear structured identity.
7. A universal three-second success timeout requires one shared hook, timer reset/cleanup, persistent errors, and fake-timer coverage across every success surface.
8. Field Map must set encounter GeoJSON on `load` and on later filter changes, refresh cluster markers after source data, visibly highlight selected evidence, and place Selected Encounter above the list in one right rail.

## Conclusion

Use local eBird hotspots first and retain Open-Meteo as bounded city fallback. Defer Overture/OSM until witnessed non-hotspot gaps justify the licensing and ingestion obligation. Store optional structured observation locations alongside free text. Repair MapLibre source readiness/highlighting/layout directly. Apply three-second auto-dismiss to all Rufous success messages as explicitly selected by the user.

## Limits

Hotspot suggestions are birding locations, not a complete Arizona gazetteer. Open-Meteo fallback remains a request-time external dependency for cities. Overture/OSM remain possible separately shaped expansions, not implicit fallback behavior.
