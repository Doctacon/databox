Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Rufous Field Map interaction repair

## Source readiness and filtering

Encounter GeoJSON MUST be applied after MapLibre `load`/source readiness and after every filtered-data change. A filter change updates source data, cluster markers, result/list/card state, and fits the filtered extent when nonempty; All snapshot reset fits Arizona. Empty filters retain Arizona framing and disclose empty state. Source/list counts must agree.

Cluster markers refresh only after source data events and remain keyboard-operable. Cluster activation visibly zooms. Point or list activation:

- sets one selected encounter;
- pans/zooms to it;
- renders a distinct selected-point highlight above encounter points;
- updates the same selected card/list pressed state;
- respects reduced motion.

## Layout

Desktop `.field-map-layout` contains:

- map panel in the left column;
- one right rail containing Selected Encounter first and Accessible Encounter List second.

Selected Encounter MUST NOT be a separate grid item below the row. At narrow widths, stack Map, Selected Encounter, then List. Right-rail list has bounded scrolling without clipping the selected card. Long text wraps normally.

## Acceptance scenarios

- Initial load shows encounter clusters/points rather than boundary-only geometry.
- Species/family/recency changes visibly change map source/count/extent.
- List selection highlights and zooms to the same point.
- Point selection updates pressed list row and selected card.
- Selected card is above the list on desktop and between map/list on mobile.
- Load races, filter changes before load, no results, back/forward, reduced motion, and cleanup are deterministic.
