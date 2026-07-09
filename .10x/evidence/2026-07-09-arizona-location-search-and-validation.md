Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-add-arizona-location-search-and-validation.md, .10x/specs/arizona-trip-location-resolution.md

# Arizona location search and validation evidence

## What was observed

The local Python API now owns bounded Open-Meteo geocoding and exposes stable Arizona-only suggestions. The React form provides a debounced, cancellable, keyboard-accessible combobox while retaining known aliases and manual coordinates.

Location validation occurs before DuckDB creation, weather/evidence lookup, model inference, or persistence. Arizona-shaped positive longitudes fail with an explicit negative-longitude suggestion and are never silently corrected. Valid manual coordinates receive `US-AZ` and `America/Phoenix`, preserving Arizona filters. A selected place's normalized name, coordinates, region, and timezone are persisted across the plan and Open-Meteo evidence, then returned by the stable API.

## Implementation observations

- `packages/databox/databox/agent_tools/arizona_boundary.py` stores a 195-point generalized Arizona polygon derived from the official public-domain US Census TIGERweb States layer (`STATE=04`, WGS84, four-decimal precision, `maxAllowableOffset=0.005`). Deterministic ray casting treats stored boundary points/segments as inside.

Boundary provenance/derivation endpoint (retrieved 2026-07-09):

```text
https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0/query?where=STATE%3D%2704%27&outFields=GEOID%2CNAME&returnGeometry=true&outSR=4326&geometryPrecision=4&maxAllowableOffset=0.005&f=geojson
```
- `packages/databox/databox/agent_tools/open_meteo_geocoding.py` normalizes `Prescott, Arizona` to the upstream place-name query `Prescott`, limits results to five, and requires both Arizona administrative identity and polygon membership.
- Direct/socket timeouts and HTTP/URL transport failures normalize to `OpenMeteoGeocodingError`; the API maps that typed failure to stable JSON without transport details.
- `GET /api/locations?q=...` returns only browser-safe typed fields and maps upstream failures to a bounded user-safe error.
- `POST /api/trip-plans` accepts an optional typed selected-location object and revalidates all coordinates/region before opening DuckDB.
- Direct planner calls also validate before creating the `birding_agent` schema.
- React waits 250 ms, requires three characters, skips coordinate-shaped values, aborts stale requests, and supports Arrow Up/Down, Enter, and Escape with combobox/listbox semantics.
- Timezone persists in the Open-Meteo evidence payload and is projected into plan detail responses without requiring a second database or physical-table migration.

## Deterministic validation

### Focused Python

```text
uv run --no-sync ruff check packages/databox/databox/agent_tools/arizona_boundary.py packages/databox/databox/agent_tools/open_meteo_geocoding.py packages/databox/databox/agents/birding_trip_planner.py packages/databox/databox/api.py tests/test_arizona_boundary.py tests/test_open_meteo_geocoding.py tests/test_birding_trip_planner.py tests/test_api.py
uv run --no-sync mypy packages/databox/databox/agent_tools/arizona_boundary.py packages/databox/databox/agent_tools/open_meteo_geocoding.py packages/databox/databox/agents/birding_trip_planner.py packages/databox/databox/api.py
uv run --no-sync pytest --no-cov -q tests/test_arizona_boundary.py tests/test_open_meteo_geocoding.py tests/test_birding_trip_planner.py tests/test_api.py
```

Results: Ruff passed; MyPy passed for four source files; all 37 focused tests passed.

The tests prove:

- suffix normalization plus administrative and polygon-based Arizona filtering,
- known inside points, inclusive boundary semantics, and outside rejection including `36.9,-114.8` and `31.3,-114.8`,
- direct timeout, socket timeout, HTTP, and URL failure normalization with manual-coordinate fallback,
- positive-longitude and outside-Arizona rejection,
- zero database/weather/model side effects for invalid coordinates,
- known `Prescott, Arizona` alias support,
- `US-AZ` and `America/Phoenix` retention,
- selected-location name/coordinate/region/timezone persistence and reload.

### Frontend

```text
cd app && npm run typecheck && npm test && npm run build
```

Result: strict TypeScript passed, all nine Vitest/jsdom tests passed, and Vite built 29 modules. Rendered tests cover keyboard selection, typed selected-location submission, stale-request cancellation, coordinate search bypass, and geocoder failure.

```text
task app:audit-bundle
```

Result: all three Cloudflare configuration names and all three configured values were absent from compiled browser assets.

### Repository

```text
task ci
task docs:build
```

Results:

- full CI passed Ruff, formatting, MyPy for 72 source files, all 209 tests, 82.48% coverage, secret scan, staging drift, and platform-health drift,
- strict MkDocs build passed after generating 16 model pages plus lineage/index.

## What this supports

- Arizona place search works through the local API without exposing a browser credential or adding another database.
- The previously observed `34.54,112.50` error fails closed before any downstream side effect.
- `34.54,-112.50` and known aliases remain available even if geocoding fails.
- Coordinate plans no longer bypass Arizona evidence filtering.
- Existing model, persistence, bundle-security, and local-only database behavior remain green.

## Limits

- The stored Census polygon is deliberately generalized at `0.005` degrees (roughly sub-kilometer scale) rather than reproducing the full TIGER boundary. This is appropriate for trip-location validation but may classify a coordinate extremely close to the legal border according to the generalized line.
- Open-Meteo geocoding remains a request-time network dependency for suggestions; known aliases and valid Arizona coordinates are offline fallbacks.
- No live geocoder call was added to CI; deterministic fixtures cover its documented response shape. Earlier shaping evidence observed the live Prescott result at approximately `34.54002,-112.4685`, timezone `America/Phoenix`.
