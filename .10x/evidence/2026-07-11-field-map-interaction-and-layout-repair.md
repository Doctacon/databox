Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-repair-field-map-interaction-and-layout.md, .10x/specs/rufous-field-map-interaction-repair.md, .10x/specs/rufous-field-map.md

# Field Map interaction and layout repair verification

## What changed

Encounter GeoJSON is now held in a latest-filter ref and applied only after MapLibre's `load` readiness event. A filter changed before load is retained and becomes the first `setData`; every subsequent filter change clears stale cluster marker buttons, updates the source, and reframes the map. Default All and a recency reset to All fit the governed Arizona bounds. Nonempty filtered views fit their exact encounter extent with bounded maximum zoom; empty results retain Arizona framing.

Cluster marker buttons rebuild only after the encounter source reports loaded data. Each `setData` increments the source generation and invalidates marker readiness. A completed move may reposition markers only when loaded `sourcedata` has confirmed that same current generation; a filter-driven `fitBounds` cannot query/re-add old features while the new generation is pending. Their displayed/accessible count comes from the current source cluster. Cluster activation uses expansion zoom. Point and list activation share one selection function, zoom above `clusterMaxZoom`, respect reduced motion, set the same card/list pressed state, and update a dedicated selected-point layer above ordinary points. Incompatible filters clear selection and the highlight filter.

The desktop grid now has the map as its left child and one right `aside`. That rail contains Selected Encounter first and Accessible Encounter List second. The existing narrow one-column layout therefore produces Map → Selected → List in DOM and visual order. The list retains bounded independent scrolling; selected content is outside that scroll region, and existing long-text wrapping remains.

## Direct race and interaction verification

The typed MapLibre adapter now records `load`, `sourcedata`, `setData`, `fitBounds`, `setFilter`, `easeTo`, source features, markers, and cleanup.

`app/src/FieldMap.test.tsx` directly proves:

- no encounter `setData` occurs before load;
- a species filter changed before load is the exact first one-feature dataset;
- initial loaded map receives all four fixture encounters when unfiltered;
- species, recency, family, reset, and empty changes keep source feature cardinality equal to UI/list count;
- stale marker buttons are removed immediately and current marker counts rebuild after encounter source readiness;
- exact old-feature `moveend` events between `setData` and matching `sourcedata` cannot re-add stale 1/4/2-count markers across 4→2→0 filter transitions;
- filtered extents and Arizona reset/empty bounds are exact;
- selected layer is above ordinary encounter points;
- list and point selection both pan to zoom 11 with zero-duration reduced motion, update the same card, pressed row, and selected filter;
- cluster button/canvas activation uses exact count and expansion zoom;
- incompatible filter clears card and highlight;
- desktop children are Map then right rail, with Selected then List inside the rail;
- local inline style has no URL/tiles/glyphs/sprite, one snapshot request is made, cleanup removes the map, and loading/error/history remain safe.

Focused map verification:

```text
cd app && npm test -- --run src/FieldMap.test.tsx src/mapApi.test.ts
22 passed
```

## Review finding resolution

The first independent review failed the change because `moveend` was gated only by initial map readiness. Since `setData` and the following filter-driven `fitBounds` are asynchronous, `moveend` could query the previous source generation before the new `sourcedata` event and temporarily restore stale count markers.

The repair adds monotonically increasing `sourceGenerationRef` and a separately invalidated `markerReadyGenerationRef`. Every data application clears markers and readiness before `setData`. Only loaded `sourcedata` for encounters confirms the current generation and rebuilds markers. `moveend` refresh is allowed only when confirmed generation equals current generation. Cleanup invalidates readiness. The adapter regression deliberately leaves old query features in place, fires `moveend`, proves zero marker buttons, then fires current `sourcedata` and proves exact current counts.

## Full gates

```text
cd app && npm test -- --run
16 files passed; 260 tests passed

cd app && npm run typecheck
passed

cd app && npm run build
passed; 52 modules transformed

.venv/bin/python scripts/audit_app_bundle.py app/dist
bundle configuration audit passed: 12 names and 10 configured values absent

PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --no-cov \
  tests/test_map_snapshot_api.py tests/test_audit_app_bundle.py tests/test_rufous_theme.py
30 passed
```

The warehouse SHA-256 matched before/after map gates:

```text
0dc79f3596c9bd5698c4c9f40d91dd0cfbda82f2093a85611c4aacfedcd003ce
```

The Vite lazy Field Map chunk-size advisory remains pre-existing and non-blocking.

## What this supports

- The initial map cannot remain boundary-only because the latest dataset is applied at load.
- Source data, marker lifecycle, result/list count, extent, selection, card, and pressed state remain synchronized.
- Selection is visibly unclustered/highlighted after list or point activation and uses reduced-motion-safe navigation.
- Desktop and narrow layout order match the governing specification without clipping the selected card.
- No new data, remote runtime resource, provider request, or personal point was introduced.
- No file was staged or committed.

## Limits

MapLibre behavior is exercised at the typed jsdom adapter boundary rather than a physical GPU canvas. Independent review remains required before closure.
