Status: done
Created: 2026-07-11
Updated: 2026-07-11

# Rufous catalog discovery and local Field Map research

## Question

How should Rufous improve Arizona catalog discovery and add a useful Pokémon-inspired mapping surface without violating local privacy, open-source-first architecture, source authority, or accessibility?

## Sources and methods

Inspected current catalog/profile API, TypeScript contracts, browser controls, profile layout CSS, active catalog/privacy decisions, and live DuckDB state. Current eligible map source contains 1,676 valid, reviewed, non-private Arizona observation rows spanning 173 species and 217 public locations, from 2026-06-08 through 2026-07-09.

External engineering sources:

- MapLibre GL JS GeoJSON clustering example: https://maplibre.org/maplibre-gl-js/docs/examples/cluster/
- MapLibre GL JS Marker API: https://maplibre.org/maplibre-gl-js/docs/API/classes/Marker/
- MapLibre GL JS project/API: https://maplibre.org/projects/gl-js/ and https://maplibre.org/maplibre-gl-js/docs/API/
- deck.gl MapLibre integration and MVT guidance: https://deck.gl/docs/developer-guide/base-maps/using-with-maplibre and https://deck.gl/docs/api-reference/geo-layers/mvt-layer
- eBird hotspot/explore interaction patterns: https://support.ebird.org/en/support/solutions/articles/48001280356-explore-ebird-hotspots, https://support.ebird.org/en/support/solutions/articles/48001255128-find-birds-with-ebird, and https://support.ebird.org/en/support/solutions/articles/48001255129-explore-regions-and-hotspots
- US Census cartographic boundary files and naming: https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html and https://www.census.gov/programs-surveys/geography/technical-documentation/naming-convention/cartographic-boundary-file.html

## Findings

1. MapLibre directly supports clustered GeoJSON sources, cluster expansion, and unclustered point interaction. At 1,676 current eligible rows, deck.gl/MVT tiling would be speculative complexity; one bounded GeoJSON response is sufficient.
2. eBird-style broad discovery benefits from clusters at statewide zoom and exact encounter details after zoom/click. Rufous should link the map and an accessible encounter list rather than make the canvas the only interface.
3. Map accessibility is not solved by marker clustering alone. Keyboard-operable filters, a synchronized semantic list, visible focus, live result counts, and list-driven map focus are required.
4. External map tiles would disclose local use and add a remote runtime dependency. A bundled local Arizona state/county geometry with a custom Rufous style avoids tile calls and fits the field-console aesthetic.
5. Census cartographic boundary files are simplified for thematic mapping and can be transformed once into a compact Arizona-only GeoJSON artifact. The source revision, transformation, fields retained, checksum, and usage terms must be recorded before committing the artifact.
6. Catalog summary rows already contain family, taxonomic order, observation count, and latest observation. Habitat and body mass are currently profile-only and must be added explicitly to the strict summary API before client-side filtering.
7. Current CSS accidentally retains the generic two-column `main` grid on bird profiles. Explicit `grid-template-columns: 1fr`, DOM reordering, and a one-column media grid solve the reported readability problems without JavaScript.

## Conclusions

Use a dedicated `/map` Field Map implemented with open-source MapLibre GL JS, local bundled Arizona geometry, and one read-only privacy-filtered API. Do not add deck.gl, remote tiles, personal observations, routing, weather, or ranges in the first slice.

Catalog discovery should remain client-side over the strict 706-row snapshot. Add only habitat and mass to summaries, then provide deterministic A–Z default sorting, approved additional sorts, and intersection filters. Alphabetize unordered text choice lists globally while preserving meaningful numeric, ordinal, and chronological orders.

## Limits

No live map was built or performance-tested. Census source terms and exact artifact checksum must be revalidated during the bounded map-data ticket. Current-clock recency can produce an empty stale map; the UI must disclose snapshot freshness and offer All snapshot as the default.
