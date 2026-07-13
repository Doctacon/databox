Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-upgrade-map-catalog-and-refresh-controls.md
Depends-On: None

# Add Field Map encounter photos and transient preview

## Scope

Extend the map snapshot with bounded deduplicated exact catalog-photo metadata; render lazy attributed thumbnails/placeholders; add pointer-hover and keyboard-focus equivalent unclustered map preview that never pans or changes persistent selection.

## Acceptance criteria

- API/media relationships and strict browser validators satisfy `.10x/specs/field-map-encounter-photo-preview.md`.
- Available, unavailable, hybrid, stale, malformed, load-failure, duplicate, and unrelated-photo cases fail/render as specified.
- Hover/focus/leave/blur/filter/unmount and same-as-selected behavior pass without stale map generations.
- Click/Enter persistent selection and existing map filters/layout remain intact.
- No GET discovery/write or remote map-resource request occurs.

## Evidence expectations

Focused API/validator/MapLibre adapter/DOM/accessibility tests, network-resource audit, TypeScript/build/bundle checks, and live read-only cardinality/identity inspection.

## Exclusions

No calls, binary cache, parent media, hover pan/selection, external basemap, or unrelated map redesign.

## Blockers

None.

## Progress and notes

- 2026-07-11: Shaped from user-ratified behavior and active media/map boundaries.

- 2026-07-11: Implemented bounded exact map photos, lazy attributed thumbnails/placeholders, and focus/hover-only unclustered preview. Live read-only snapshot: 1,575 encounters, 152 photo identities, 139 available.
- 2026-07-11: Evidence: `.10x/evidence/2026-07-11-map-wheel-refresh-controls-implementation.md`. Parent executed directly because the session-wide subagent spawn limit was already 40/40.
