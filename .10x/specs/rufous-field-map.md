Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Rufous Field Map

## Purpose and route

Rufous MUST provide a dedicated `/map` top-level **Field Map** for statewide discovery from persisted public Arizona observation evidence. It is not a range map and does not imply presence beyond the displayed evidence.

## Open local map architecture

- Use open-source MapLibre GL JS.
- The style, sprites if any, state/county geometry, and application assets MUST be bundled locally. Browser runtime MUST make no tile, style, glyph, telemetry, or provider request.
- A bounded official US Census cartographic-boundary source MUST be transformed to Arizona-only state/county GeoJSON at `app/src/assets/arizona-boundaries.geojson`. Record source revision, terms, transformation command, retained fields, row count, and SHA-256. Do not commit unrelated national geometry. The eventual map source disclosure MUST identify the U.S. Census Bureau source, say the artifact is derived/modified, and state that the product is not endorsed or certified by the Census Bureau.
- Do not add deck.gl, routing, terrain, remote tiles, or PMTiles in this slice.

## Observation API

`GET /api/map-snapshot` is the selected local internal interface. It returns one typed read-only snapshot with at most 10,000 encounters. The query MUST inspect up to 10,001 eligible rows and fail closed with a safe 503 rather than truncate when the bound is exceeded:

- snapshot latest observation and source freshness;
- exact eligible rows from current modeled Arizona observation evidence where region is `US-AZ`, coordinates are within the governed Arizona bounds, `is_valid=true`, `is_reviewed=true`, and `is_location_private=false`;
- source record ID or deterministic evidence ID, exact species code/current display identity/family, observation timestamp/count/notable flag, public location ID/name, latitude/longitude, and access-warning boolean.

Missing, blank, duplicate, malformed, non-current identity, impossible timestamp/count/coordinates, or privacy ambiguity fails closed. `(private)` in an otherwise public location name sets access warning and does not reclassify source privacy. GET performs no writes, model/weather/provider calls, or discovery. Personal observations, Watches, plans, credentials, media, traces, and raw arbitrary evidence are excluded.

## Filters and current-clock recency

Default controls:

- Species: All species, then alphabetized eligible current species.
- Family: All families, then alphabetized exact family labels.
- Recency: All snapshot (default), Last 48 hours, Last 7 days, Last 30 days.

Recency uses the browser/computer current clock at evaluation time and includes rows with `observation_datetime >= now - window`. The UI MUST show source freshness and explicitly explain when current-clock filtering returns zero because the local snapshot is stale. Species and family combine with recency using AND.

## Map interaction

- Initial view fits Arizona.
- GeoJSON points cluster at statewide/intermediate zoom. Cluster display communicates eligible row count only.
- Activating a cluster zooms to expansion; activating a point selects it.
- Selected encounter card shows bird, public location, observation time/count/notable state, access warning, and link to bird profile.
- Selection and result count are announced without moving focus unexpectedly.
- Filters clear incompatible selection and recompute clusters.

## Accessible equivalent

The canvas MUST NOT be the sole interface. A synchronized semantic encounter list provides the same filtered rows, selectable by keyboard, with a control to focus the corresponding map point. Map controls have accessible names; visible focus, reduced motion, high contrast, 320px stacked layout, empty/error/loading states, and long labels are required.

## Acceptance scenarios

- Initial GET/current snapshot renders eligible rows and no third-party request.
- A private, invalid, unreviewed, duplicate, out-of-bounds, malformed, or unknown-taxon row cannot reach API or map.
- All snapshot remains useful when the source is stale; 48-hour/current-clock view can show a disclosed empty state.
- Cluster activation zooms; list selection and point selection show the same safe card.
- Public location name containing `(private)` displays an access warning.
- Direct `/map`, navigation, back/forward, keyboard, and 320px layouts work.

## Explicit exclusions

No inferred range polygon, predicted habitat, personal observation/watch map, trip route, directions, weather, provider lookup, external basemap, offline national tile archive, or claim of current presence.
