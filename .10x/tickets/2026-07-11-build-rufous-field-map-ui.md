Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-build-field-map-data-api.md

# Build Rufous Field Map UI

## Scope

Implement `/map`, navigation, open-source MapLibre local style/geometry, clusters, species/family/current-clock recency controls, selected encounter card, and synchronized accessible list under `.10x/specs/rufous-field-map.md`.

## Acceptance criteria

- Initial view fits Arizona and default All snapshot; filters are exact and text options alphabetical.
- 48h/7d/30d use current clock and disclose stale/empty state and source freshness.
- Cluster activation zooms; point/list selection agrees and links to exact profile with access warning where needed.
- Browser makes zero third-party tile/style/glyph/font/telemetry request; bundle audit proves no secret/config leak.
- Semantic list provides equivalent keyboard access; focus/live count/reduced motion/contrast/320px/loading/error/empty/history/direct route pass.
- No extra rendering dependency beyond MapLibre and no personal/range/route/weather behavior.

## Exclusions

No deck.gl, PMTiles, remote basemap, directions, personal map, trip map, or predicted habitat/range.

## Evidence expectations

Record request audit, clusters/selection/filter/current-clock matrices, semantic equivalence, responsive/accessibility, dependency/license/bundle and full frontend gates.

## Blockers

Depends on map API and local geometry.
