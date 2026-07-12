Status: open
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
4. `.10x/tickets/2026-07-11-auto-dismiss-rufous-success-messages.md`
5. `.10x/tickets/2026-07-11-repair-field-map-interaction-and-layout.md`
6. `.10x/tickets/2026-07-11-verify-place-search-feedback-and-map.md`

Hotspot search, success feedback, and map repair are parallelizable. Observation persistence depends on suggestion identity; observation UI depends on both. Aggregate verification follows every child.

## Acceptance

- `lake watson` returns the local Watson Lake hotspot and all workflows reuse strict source-labeled suggestions.
- Observations preserve structured selection or free text atomically and privately.
- Every success banner disappears after 3,000 ms; errors/persistent states do not.
- Field Map loads visible encounter data, reacts to filters/selections, and places Selected Encounter above the right-hand list.
- Full privacy/data/frontend/backend/docs/static gates and independent reviews pass without deleting current personal state.

## Blockers

None; execute only after implementation authorization.
