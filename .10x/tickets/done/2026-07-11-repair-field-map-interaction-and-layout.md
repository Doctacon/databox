Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-upgrade-place-search-feedback-and-map.md
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

## Progress and notes

- 2026-07-11: Repaired source readiness by retaining latest filtered rows and applying them on MapLibre load, then after every filter. Added synchronized source/marker cleanup, filtered extent fitting, Arizona All/empty framing, and pre-load filter race handling.
- 2026-07-11: Added a selected-point layer above ordinary points and one shared point/list selection path that zooms above cluster max zoom, pans, respects reduced motion, updates card/pressed/highlight state, and clears on incompatible filters. Cluster activation remains count-labeled and expansion-zoomed.
- 2026-07-11: Moved Selected Encounter above Accessible Encounter List inside one right rail beside the desktop map; the existing narrow grid stacks Map → Selected → List. Added direct adapter/layout/request/accessibility tests.
- 2026-07-11: Focused map passed 22/22; full frontend passed 260/260 plus typecheck/build/bundle audit; backend map/audit/responsive gates passed 30/30 with unchanged warehouse hash. Evidence: `.10x/evidence/2026-07-11-field-map-interaction-and-layout-repair.md`.
- 2026-07-11: Independent review found `moveend` could query stale features between `setData` and current `sourcedata`. Added per-update source/marker generation readiness: every apply invalidates marker readiness, only loaded encounter `sourcedata` confirms the current generation, and `moveend` is ignored while pending. Added exact old-feature moveend-before-sourcedata regression across 4→2→0 filters. Focused map passed 22/22 again; full frontend passed 260/260 plus typecheck/build/bundle audit; backend map/audit/responsive passed 30/30.
- 2026-07-11: Independent follow-up review passed. Review: `.10x/reviews/2026-07-11-field-map-interaction-layout-repair-review.md`.
- 2026-07-11: Retrospective preserved MapLibre asynchronous source generations and marker readiness as an explicit regression; no additional record is needed.
