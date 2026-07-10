Status: open
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/2026-07-10-implement-personal-bird-collection-storage-and-api.md

# Build My Birds and profile collection controls

## Scope

Implement the React “My Birds” navigation and Life List, Observations, Wishlist, and Watches surfaces plus explicit species-profile controls governed by `.10x/specs/personal-bird-collection.md`.

Use strict runtime API validation, local catalog species selection, native forms/confirmation/dialog semantics, route title/focus/history behavior, responsive states, and clear independence among observed/wishlist/watch state.

## Acceptance criteria

- Navigation/direct/back-forward routes preserve Trip Planner and Arizona Birds behavior.
- Observation create/edit/hard-delete flows require species/date, support optional location/notes, confirm deletion, and refresh derived life-list state.
- Wishlist and watch add/remove/pause/resume/edit controls are explicit, idempotent, and never mutate another state.
- Watch forms use validated Arizona center selection and 1–300-mile radius; no global origin is implied.
- Hybrid/stale/empty/loading/error/busy states, keyboard/focus behavior, responsive layout, and non-color status cues pass.
- Browser bundle, logs, rendered errors, and tests contain no personal fixture values or server credentials; existing planner/catalog/media tests remain green.

## Explicit exclusions

No match evaluation, target planning, weather/model call, calendar/outbox/SMTP side effect, map, remote account, or eBird import.

## Evidence expectations

Record exact UI/API mapping, route/accessibility behavior, state independence, confirmations, sparse/error cases, bundle/secret scan, and complete frontend regression.

## Progress and notes

- 2026-07-10: Ticket depends on the collection API contract and owns only browser presentation/mutations.

## Blockers

None.
