Status: done
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

## Progress and notes

- 2026-07-11: Added open-source `maplibre-gl` 5.24.0 (BSD-3-Clause) as the only map renderer; no deck.gl, Mapbox, remote tile, glyph, font, style, sprite, telemetry, routing, weather, personal, or range dependency/behavior was added. Map code and CSS are lazy-loaded only on `/map`.
- 2026-07-11: Implemented direct/history/native navigation, `Field Map · Rufous` title/focus, inline local Census state/county geometry/style, Arizona fit, filtered clustered GeoJSON, exact-count keyboard cluster markers, point/list selection, safe encounter card/profile link/access warning, and cleanup.
- 2026-07-11: Added alphabetized exact species/family filters and ordinal recency control. All snapshot defaults; 48-hour/7-day/30-day current-clock windows combine with species/family using AND, clear incompatible selection, retain source freshness, and disclose stale-window empty state.
- 2026-07-11: Added synchronized semantic keyboard list, polite eligible/selection updates, safe loading/error/empty states, normal long-label wrapping, 44px controls, reduced-motion zero-duration map motion, high-contrast inheritance, desktop/820px/320px contracts, and Census derived/non-endorsement disclosure.
- 2026-07-11: Added bundle rejection for common remote map runtime hosts. Focused map/API/select tests pass 24/24; full frontend passes 249/249 plus typecheck/build/bundle audit; targeted backend/privacy/static gates pass 29/29; MapLibre license and zero-vulnerability production audit pass. Evidence: `.10x/evidence/2026-07-11-rufous-field-map-ui.md`.

- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-rufous-field-map-ui-review.md`.
- 2026-07-11: Retrospective preserved local-resource and semantic-list equivalence as bundle/interaction regressions; no additional record is needed.

## Blockers

None.
