Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-upgrade-place-search-feedback-and-map.md
Depends-On: .10x/tickets/done/2026-07-11-persist-structured-observation-locations.md

# Add observation location combobox

## Scope

Reuse the strict location combobox in new/edit observation forms while preserving optional free text and structured selection semantics.

## Acceptance criteria

- User can select Watson Lake and save exact structured data, or type/save unselected private text.
- Editing selected text clears selection; selecting another place replaces it; existing structured/free-text rows initialize correctly.
- Failed save preserves text/selection and focuses safe error; success invalidates collection state once.
- Keyboard/listbox/cancellation/loading/upstream-fallback/320px behavior and observation CRUD remain accessible.
- Full frontend/type/build/bundle/collection/privacy gates pass.

## Exclusions

No required location, background/reverse geocoding, personal map, or storage/API behavior beyond completed contract.

## Evidence expectations

Record structured/free-text create/edit/reset/failure/direct profile/My Birds cases and full gates/review.

## Blockers

None. The structured observation API is complete.

## Progress and notes

- 2026-07-11: Reused `LocationCombobox` in new/edit My Birds and direct-profile observation forms with optional private free text. Exact selected suggestions are submitted, typed edits clear selection, replacements overwrite it, and structured/free-text rows initialize correctly.
- 2026-07-11: Added My Birds/profile coverage for Watson keyboard selection, exact payloads, reset, structured/free-text initialization, clear, replacement, one invalidation per success, and selected failure preservation/safe error focus. Existing shared tests cover loading, cancellation, direct coordinates, fallback, and listbox behavior; responsive contracts passed 4/4.
- 2026-07-11: Full frontend passed 253/253 after the separately authorized Target Bird focus-test stabilization, plus typecheck, build, bundle audit, 58/58 collection/privacy tests, and unchanged live warehouse/one-observation checksum. Evidence: `.10x/evidence/2026-07-11-observation-location-combobox.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-observation-location-combobox-review.md`.
- 2026-07-11: Retrospective preserved structured/free-text selection lifecycle in shared component and form regressions; no additional record is needed.
