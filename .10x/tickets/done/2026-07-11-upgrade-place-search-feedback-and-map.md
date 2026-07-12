Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: None
Depends-On: .10x/tickets/done/2026-07-11-improve-catalog-and-add-field-map.md

# Upgrade place search, feedback, and Field Map interaction

## Aggregate outcome

Add birding-place-first Arizona autocomplete to all location workflows, persist optional structured observation locations, auto-dismiss every Rufous success message after three seconds, and repair Field Map source/selection/layout behavior.

This parent is not executable directly.

## Governing records

- `.10x/decisions/rufous-local-place-suggestions-and-feedback.md`
- `.10x/decisions/rufous-local-hotspot-fallback-policy.md`
- `.10x/specs/arizona-place-suggestions.md`
- `.10x/specs/structured-observation-locations.md`
- `.10x/specs/transient-success-feedback.md`
- `.10x/specs/rufous-field-map-interaction-repair.md`
- `.10x/specs/personal-bird-collection.md`
- `.10x/research/2026-07-11-rufous-place-search-and-map-interaction.md`

## Child sequence

1. `.10x/tickets/done/2026-07-11-add-local-hotspot-place-suggestions.md`
2. `.10x/tickets/done/2026-07-11-persist-structured-observation-locations.md`
3. `.10x/tickets/done/2026-07-11-add-observation-location-combobox.md`
4. `.10x/tickets/done/2026-07-11-auto-dismiss-rufous-success-messages.md`
5. `.10x/tickets/done/2026-07-11-repair-field-map-interaction-and-layout.md`
6. `.10x/tickets/done/2026-07-11-verify-place-search-feedback-and-map.md`

Discovered bounded child:

7. `.10x/tickets/done/2026-07-11-stabilize-target-bird-heading-focus-test.md`

Hotspot search, success feedback, and map repair are parallelizable. Observation persistence depends on suggestion identity; observation UI depends on both. Aggregate verification follows every child.

## Acceptance

- `lake watson` returns the local Watson Lake hotspot and all workflows reuse strict source-labeled suggestions.
- Observations preserve structured selection or free text atomically and privately.
- Every success banner disappears after 3,000 ms; errors/persistent states do not.
- Field Map loads visible encounter data, reacts to filters/selections, and places Selected Encounter above the right-hand list.
- Full privacy/data/frontend/backend/docs/static gates and independent reviews pass without deleting current personal state.

## Progress and notes

- 2026-07-11: All seven planned/discovered direct children are done with evidence and pass reviews.
- 2026-07-11: Local hotspot suggestions resolve both Watson token orders with zero upstream; optional structured/free-text observations preserve the existing personal row; all success banners use one 3,000-ms owner; Field Map source generation, highlight, and right-rail layout are repaired.
- 2026-07-11: Aggregate verification passed 709 network-blocked Python tests, 260 frontend tests, 13 SQLMesh tests, 25 Soda contracts/125 checks, and all type/build/bundle/docs/static/hooks gates with warehouse, SQLMesh state, and personal checksum unchanged.
- 2026-07-11: Four aggregate architecture, correctness, privacy/security/source, and UX/accessibility reviews passed.
- 2026-07-11: Retrospective preserved fallback/dedup supersession, structured migration safety, universal timer inventory, MapLibre source generations, and lazy-focus timing in durable records/tests. Physical browser/screenshot/assistive-technology and live provider calls remain explicit accepted evidence limits.
- 2026-07-11: Independent parent closure review passed. Review: `.10x/reviews/2026-07-11-place-search-feedback-map-parent-closure-review.md`.

## Blockers

None.
