Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-build-rufous-field-map-ui.md, .10x/specs/rufous-field-map.md, .10x/decisions/rufous-catalog-discovery-and-field-map.md

# Rufous Field Map UI evidence

## Implementation boundary

`/map` is a dedicated native-history route and primary-navigation item with title `Field Map · Rufous`. It lazy-loads `FieldMap.tsx`, MapLibre code, and MapLibre CSS only when used. The map uses:

- `maplibre-gl` 5.24.0, BSD-3-Clause, from `https://github.com/maplibre/maplibre-gl-js`;
- inline parsed `app/src/assets/arizona-boundaries.geojson` state/county geometry;
- an inline style containing only background/fill/line/circle layers;
- one local `/api/map-snapshot` fetch;
- no tile URL, glyph URL, font URL, sprite URL, telemetry endpoint, Mapbox SDK, deck.gl, PMTiles, routing, weather, personal collection, plan, Watch, or inferred range data.

The initial map fits governed Arizona bounds. Filtered exact encounter points are supplied as in-memory GeoJSON with MapLibre clustering. Cluster counts use local HTML buttons rather than a glyph-dependent symbol layer, so the visible/accessible label communicates only the eligible encounter count and never initiates a glyph request.

## Interaction and filter matrix

A fixed-clock four-row adversarial snapshot proves:

```text
All snapshot: 4
Last 48 hours: 2
Last 7 days: 3
Last 30 days: 4
48 hours AND Alpha Family: 0, with stale/current-clock disclosure
All snapshot AND Alpha Family: 2
All snapshot AND Alpha Family AND alpha10: 1
```

Species options are `All species`, `Alpha 2`, `alpha 10`, `Beta`, `Gamma scientific`, proving case-insensitive numeric ordering and scientific fallback. Family options are `All families`, `Alpha Family`, `Fixtureidae`, `Zebra Family`, proving exact deduplication, alphabetical ordering, and scientific fallback. Recency remains semantic/ordinal rather than alphabetized.

Default state is All snapshot. Recency evaluates `Date.now()` when controls recompute and combines with species/family using AND. Current-clock zero results explicitly say the local snapshot may be stale and direct the user back to All snapshot. Latest encounter and source freshness remain visible.

## Map/list semantic equivalence

Tests prove:

- selecting a semantic list button selects the exact evidence ID, marks the button pressed, moves the map to that point, and shows the same bird/location/time/count/notable data in the selected card;
- a MapLibre unclustered-point event selects the same card/list row;
- incompatible filter changes clear selection;
- a cluster of 23 rows renders a keyboard button labeled `Zoom to cluster containing 23 eligible encounters`, requests exact expansion zoom, and uses zero-duration motion when reduced motion is requested;
- the selected card links through native history to the exact `/birds/{species_code}` profile;
- a public-authority `(private)` name renders the governed access warning in list and selected card;
- map removal runs on route/history cleanup.

The semantic ordered list contains every filtered encounter, so the canvas is not the sole interface. Result count and selected card are polite live regions. The route heading receives focus without moving focus on selection.

## Locality, accessibility, and responsive contracts

The captured actual style object contains all 15 Arizona county names and no `http`, `tiles`, `glyphs`, or `sprite` member. The only fetch observed by the rendered map is `/api/map-snapshot`. The production bundle audit now rejects `api.mapbox.com`, `tiles.mapbox.com`, `tile.openstreetmap.org`, `demotiles.maplibre.org`, and `fonts.googleapis.com`; the built bundle passes.

CSS tests pin:

- desktop map/list columns;
- one column at 820px;
- one-column filters, four-column compact navigation, 12px page padding, and 360px map height at the 320px-supported breakpoint;
- normal `break-word`/`word-break: normal` long-label wrapping;
- 44px MapLibre and cluster controls;
- visible canvas focus;
- reduced-motion and increased/forced-contrast rules.

Loading, safe API error, zero general-filter results, zero stale-window results, direct route, title, heading focus, navigation current state, native history, and cleanup are rendered tests. Custom Census source/modification/non-endorsement disclosure remains visible.

## Dependency, license, and build evidence

```text
maplibre-gl 5.24.0 BSD-3-Clause https://github.com/maplibre/maplibre-gl-js
npm audit --omit=dev: 0 vulnerabilities
npm ls maplibre-gl @deck.gl/core mapbox-gl --depth=0:
  maplibre-gl@5.24.0 only
```

Vite emits the existing application shell separately from map code:

```text
index JS: 267.53 kB (78.30 kB gzip)
FieldMap JS/MapLibre: 1,098.95 kB (295.69 kB gzip), loaded only on /map
index CSS: 19.66 kB
FieldMap CSS: 69.94 kB, loaded only on /map
```

MapLibre's self-contained renderer produces Vite's advisory large lazy-chunk warning; it does not fail the build or load on other Rufous routes.

## Verification

- `cd app && npm run typecheck && npm test -- --run` — TypeScript and 249/249 tests passed across 15 files.
- Focused `FieldMap`, map API, and dropdown inventory — 24/24 passed.
- `cd app && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — production build and expanded configuration/remote-map-runtime audit passed; 12 names and ten configured values absent.
- Targeted backend map snapshot, geometry, static responsive/direct-route, and bundle-audit tests — 29/29 passed.
- Targeted Ruff/format and repository secret scan passed.
- `npm audit --omit=dev`, exact MapLibre license assertion, and absence of deck.gl/Mapbox passed.
- `git diff --check` and empty cached-diff assertion passed; no stage or commit occurred.

## Limits

Map rendering behavior is tested through the typed MapLibre adapter boundary in jsdom rather than a GPU/browser screenshot. Exact map style/source locality, event semantics, rendered accessible equivalent, and production bundle are covered, but physical-device visual rendering remains an independent-review residual. Independent review remains required before closure.
