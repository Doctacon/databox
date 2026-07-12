Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-upgrade-place-search-feedback-and-map.md
Depends-On: .10x/tickets/done/2026-07-11-build-rufous-field-map-ui.md

# Repair Field Map interaction and layout

## Scope

Implement `.10x/specs/rufous-field-map-interaction-repair.md`: source-load race fix, filter extent/data/marker refresh, selected highlight and pan/zoom, synchronized selection, and right rail with Selected Encounter above list.

## Acceptance criteria

- Initial map visibly receives all encounter data after load; no boundary-only race.
- Every filter change updates source/count/markers/extent; All reset fits Arizona.
- Cluster, point, and list activation visibly zoom/highlight and synchronize card/pressed state.
- Desktop map/right rail and narrow Map→Selected→List order are exact; scrolling/long text work.
- Cleanup, no results, history, reduced motion, local-only request audit, and full map/frontend gates pass.

## Exclusions

No new map source/data, basemap, Overture/OSM, routing, personal points, weather, or range inference.

## Evidence expectations

Record direct race reproduction, MapLibre event/source calls, selection/filter/layout matrices, accessibility/request audit/review.

## Blockers

None.
