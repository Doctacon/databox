Status: open
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

Depends on structured observation API.
